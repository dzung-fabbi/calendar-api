"""Turning resolved facts into a Vietnamese kinship word.

Pure lookup over `kinship_terms`, split from `services/kinship.py` so the
"which word" rules sit apart from the "which people" ones.

THE ONE RULE THIS FILE EXISTS TO ENFORCE: never guess. `TERMS` only holds an
entry under a `None` slot where that fact genuinely does not change the word.
So a missing `birth_order` finds nothing, falls through to `AMBIGUOUS_TERMS`
and comes back as `bác/chú` with `confident: False` -- because getting vai vế
wrong is an insult, and an honest hedge is the better answer.

THE RULE IS "NEVER GUESS", NOT "ALWAYS HEDGE". A hedge that lists an option
the known facts have already ruled out is not honesty, it is noise: it can
even contradict the confident word travelling in the other direction of the
same answer. Both tables are therefore widened by ONE generator over the
same five slots, so a hedge is as specific as the facts allow.
"""

from giapha.services.kinship_terms import (
    AMBIGUOUS_TERMS,
    GENERIC_ANCESTOR,
    GENERIC_DESCENDANT,
    MAX_TABLE_GAP,
    REASON_MISSING_GENDER,
    REASON_OUT_OF_TABLE,
    TERMS,
)

KNOWN_GENDERS = ('nam', 'nu')


def gender_of(by_id, person_id):
    row = by_id.get(person_id)
    return row['gioi_tinh'] if row else None


def name_of(by_id, person_id):
    """`ho_ten`, or the bare id as a last resort -- `explain` must never crash
    on a person the row set does not contain.
    """
    row = by_id.get(person_id)
    return row['ho_ten'] if row else str(person_id)


def is_elder(by_id, via_self, via_other):
    """True when `via_other`'s branch is the ELDER of the common ancestor's
    two children, False when younger, `None` when it cannot be told.

    Seniority between branches, not between people: `con của bác` outranks
    you even if born later, which is why this compares the two children of
    the common ancestor rather than the two people being asked about.

    `None` on a missing OR an equal `birth_order`. Two siblings sharing a
    `birth_order` is corrupt data, and picking one of them would be exactly
    the confidently-wrong answer this endpoint must never produce.
    """
    if via_self is None or via_other is None:
        return None
    self_row = by_id.get(via_self)
    other_row = by_id.get(via_other)
    if self_row is None or other_row is None:
        return None
    self_order = self_row['birth_order']
    other_order = other_row['birth_order']
    if self_order is None or other_order is None or self_order == other_order:
        return None
    return other_order < self_order


def _widenings(side, gender):
    """`(side, gender)` from most to least specific.

    Feeds `_candidate_keys`, which both lookups below now go through. It
    was not shared once: the hedge lookup widened `gender` only, so every
    `AMBIGUOUS_TERMS` row written with `side=None` at a gap where `side` is
    always known was dead code -- two un-ranked brothers got no word at all.
    One widening rule, one place.
    """
    for one_gender in (gender, None):
        for one_side in (side, None):
            yield one_side, one_gender


def _candidate_keys(kind, gap, side, gender, elder):
    """Table keys from most to least specific. A `None` slot means "this word
    does not depend on that fact"; falling back to such an entry is correct
    precisely because it was written on purpose.

    ONE GENERATOR FOR BOTH TABLES. `AMBIGUOUS_TERMS` keys on the same five
    slots as `TERMS`, so the hedge lookup below walks these same keys --
    which is what lets a hedge drop the options seniority has ruled out
    (`anh/chị`, not `anh/chị/em`, when B's branch is known to be the elder).
    """
    for one_side, one_gender in _widenings(side, gender):
        for one_elder in (elder, None):
            yield (kind, gap, one_side, one_gender, one_elder)


def resolve_term(kind, gap, side, gender, elder):
    """`{'term', 'confident', 'reason'}` for one direction of a pair.

    `term` may be `None`: that is the answer when not even a hedge would be
    defensible, and it is still a 200 for the caller.
    """
    if gender not in KNOWN_GENDERS:
        # 'khac' or a blank carries no information about the word to use.
        gender = None
    for key in _candidate_keys(kind, gap, side, gender, elder):
        term = TERMS.get(key)
        if term is not None:
            return {'term': term, 'confident': True, 'reason': None}

    for key in _candidate_keys(kind, gap, side, gender, elder):
        hedge = AMBIGUOUS_TERMS.get(key)
        if hedge is not None:
            return {'term': hedge[0], 'confident': False, 'reason': hedge[1]}

    # Past the spelled-out ladder the generic words are still exactly right,
    # and they need neither gender nor seniority.
    if gap > MAX_TABLE_GAP:
        return {'term': GENERIC_ANCESTOR, 'confident': True, 'reason': None}
    if gap < -MAX_TABLE_GAP:
        return {'term': GENERIC_DESCENDANT, 'confident': True, 'reason': None}
    if gender is None:
        return {'term': None, 'confident': False, 'reason': REASON_MISSING_GENDER}
    return {'term': None, 'confident': False, 'reason': REASON_OUT_OF_TABLE}
