"""The marriage half of the xưng-hô calculator: thím / mợ / dượng / vợ chồng.

Pure. Reached only when the blood walk found nothing, because a marriage edge
can never override a blood link that exists.

TWO DIRECTIONS, ONE RULE
------------------------
B may have married into the family (the ordinary "what do I call my uncle's
wife?"), or A may have (the con dâu asking about her husband's family). Both
are the same walk with the arguments swapped, so `affinal` calls one function
twice and swaps the result back rather than growing a second implementation.

WHICH SPOUSE THE WALK RUNS THROUGH IS A DECISION, NOT AN ACCIDENT
-----------------------------------------------------------------
A widow who remarried has two rows on record (`clan_spouse_pairs` keeps
`goa` on purpose) and a polygamous husband has several.
`kinship_marriage_rows.ranked_spouses_of` states the order once and this
module hedges when even that order leaves two rows tied. It used to be the
autoincrement id, i.e. data-entry order, which told the wife of a younger
brother to call his elder brother `em`.

A LINK WITHOUT A WORD IS STILL A LINK
-------------------------------------
Vietnamese has no everyday term for some in-laws (a stepmother, the spouse of
a `kỵ`). Those answer `term: None, confident: False,
REASON_AFFINAL_NO_TERM`, naming the spouse the link runs through -- NOT
`khong_cung_huyet_thong`, which asserts there is no relation at all.
"""

from giapha.services.kinship_blood import EMPTY_PATH, blood_result, result
from giapha.services.kinship_explain import explain_affinal, explain_affinal_mirrored
from giapha.services.kinship_graph import ancestor_index, best_common_ancestor
from giapha.services.kinship_lookup import KNOWN_GENDERS, gender_of, name_of
from giapha.services.kinship_affinal_terms import (
    AFFINAL_TERMS,
    MARRIED_IN_SUBSTITUTES,
    SPOUSE_TERMS,
)
from giapha.services.kinship_marriage_rows import ranked_spouses_of, spouses_of
from giapha.services.kinship_terms import (
    REASON_AFFINAL_NO_TERM,
    REASON_AMBIGUOUS_MARRIAGE,
    REASON_MISSING_GENDER,
)

# Re-exported so `services.kinship` keeps one import for the marriage half.
__all__ = ['affinal', 'married_couple', 'spouses_of']


def _spouse_term(by_id, person_id):
    """`vợ` / `chồng` -- used only when A and B are married to each other."""
    gender = gender_of(by_id, person_id)
    known = gender in KNOWN_GENDERS
    return {
        'term': SPOUSE_TERMS.get(gender),
        'confident': known,
        'reason': None if known else REASON_MISSING_GENDER,
    }


def married_couple(by_id, a_id, b_id):
    a_calls_b = _spouse_term(by_id, b_id)
    b_calls_a = _spouse_term(by_id, a_id)
    return result(
        a_calls_b, b_calls_a, None, dict(EMPTY_PATH),
        explain_affinal(
            name_of(by_id, a_id), name_of(by_id, b_id), None, None,
            a_calls_b, b_calls_a,
        ),
    )


def _married_in_entry(blood_entry):
    """The blood relative's own word, borrowed by the person who married in.

    "Gọi theo chồng/vợ" -- with the one substitution `MARRIED_IN_SUBSTITUTES`
    spells out: `nội`/`ngoại` asserts descent the speaker does not have.
    """
    entry = dict(blood_entry)
    entry['term'] = MARRIED_IN_SUBSTITUTES.get(entry['term'], entry['term'])
    return entry


def _doubted(entry, reason):
    """The same entry, no longer claiming to be certain."""
    hedged = dict(entry)
    hedged['confident'] = False
    hedged['reason'] = reason
    return hedged


def _candidates(rows, by_id, index_a, a_id, b_id, spouses):
    """One tuple per spouse of B that A has a blood link to, best-ranked
    first: `(rank, spouse_id, a_term, b_term, spouse_term, borrowed_from)`.

    `spouse_term` is A's word for that spouse and `borrowed_from` is the
    spouse's word for A -- the two words `explain` needs to show its work.
    """
    found = []
    for rank, spouse_id in ranked_spouses_of(spouses, b_id):
        if spouse_id not in by_id:
            continue
        index_s = ancestor_index(rows, spouse_id)
        via = best_common_ancestor(index_a, index_s)
        if via is None:
            continue
        blood = blood_result(by_id, index_a, index_s, via, a_id, spouse_id)
        spouse_term = blood['a_calls_b']['term']
        term = AFFINAL_TERMS.get((spouse_term, gender_of(by_id, b_id)))
        # The in-law word is exactly as certain as the blood word it came
        # from -- a hedged `bác/chú` yields a hedged `bác gái/thím`.
        a_term = {
            'term': term,
            'confident': term is not None and blood['a_calls_b']['confident'],
            'reason': blood['a_calls_b']['reason'] if term else REASON_AFFINAL_NO_TERM,
        }
        found.append((
            rank, spouse_id, a_term, _married_in_entry(blood['b_calls_a']),
            spouse_term, blood['b_calls_a']['term'],
        ))
    return found


def _through_marriage(rows, by_id, index_a, a_id, b_id, spouses, mirrored=False):
    """A's term for B, taken from the person B is married to.

    `None` when B has no spouse with a blood link to A at all. When such a
    spouse exists but `AFFINAL_TERMS` has no word for the pair, the answer is
    the hedge described in the module docstring; a named word from a
    lower-ranked spouse still wins over it.

    `mirrored` says B is the blood relative and A is the one who married in,
    so the two directions are transposed and the sentence is written from
    A's side. Reusing the other sentence printed an `explain` that argued
    for `b_calls_a` next to a displayed `a_calls_b`.

    `common_ancestor`/`path` are left EMPTY on purpose. They would describe
    the walk between A and B's SPOUSE, so `b_up` would count generations for
    someone not descended from that ancestor at all, and a client drawing the
    path would draw a line to a person who is not on it.
    """
    found = _candidates(rows, by_id, index_a, a_id, b_id, spouses)
    if not found:
        return None
    chosen = next((one for one in found if one[2]['term'] is not None), found[0])
    rank, spouse_id, a_term, b_term, spouse_term, borrowed_from = chosen
    # Two marriages the data ranks EQUALLY: only the id told them apart, and
    # an id is not a fact about the family. Keep the word, drop the claim.
    if any(one[0] == rank and one[2]['term'] != a_term['term'] for one in found):
        a_term = _doubted(a_term, REASON_AMBIGUOUS_MARRIAGE)
        b_term = _doubted(b_term, REASON_AMBIGUOUS_MARRIAGE)

    names = (name_of(by_id, a_id), name_of(by_id, b_id), name_of(by_id, spouse_id))
    if mirrored:
        return result(
            b_term, a_term, None, dict(EMPTY_PATH),
            explain_affinal_mirrored(
                names[1], names[0], names[2], borrowed_from, b_term['term'],
                b_term, a_term,
            ),
        )
    return result(
        a_term, b_term, None, dict(EMPTY_PATH),
        explain_affinal(names[0], names[1], names[2], spouse_term, a_term, b_term),
    )


def _named(answer):
    """True when both directions came back with an actual word."""
    return bool(answer and answer['a_calls_b']['term'] and answer['b_calls_a']['term'])


def affinal(rows, by_id, index_a, index_b, a_id, b_id, spouses):
    """The marriage walk on B's side, then the mirror image on A's.

    A MEMBER WHO MARRIED INTO THE CLAN has no blood link to anybody, so the
    B-side walk finds nothing for them -- and since `a` defaults to the
    caller's own binding, they are the people most likely to be asking. Their
    answer comes from their own spouse instead.

    When BOTH A and B married in, neither walk finds a blood link and the
    caller falls through to `khong_cung_huyet_thong`. Naming that relation
    needs two marriage hops (chị dâu = wife of my husband's brother) plus a
    rule for which spouse to route through; out of scope for this phase.
    """
    answer = _through_marriage(rows, by_id, index_a, a_id, b_id, spouses)
    if _named(answer):
        return answer
    mirrored = _through_marriage(
        rows, by_id, index_b, b_id, a_id, spouses, mirrored=True,
    )
    if _named(mirrored):
        return mirrored
    return answer if answer is not None else mirrored
