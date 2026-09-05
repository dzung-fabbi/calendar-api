"""Reading the marriage rows: who is married to whom, and WHICH marriage wins.

Pure, ORM-free. The input is exactly what `selectors.marriage.clan_spouse_pairs`
returns -- `(husband_id, wife_id, status, order)` -- and nothing here knows a
single kinship word.

Split out of `kinship_affinal.py` when that file crossed the 200-line house
rule. It is a real seam: "which marriage do we answer through" is a policy
about the family, decided once here, while the rest of that module is about
which Vietnamese word comes out of it.
"""

WIDOWED = 'goa'
# A row with no `order` recorded is read as the first marriage, matching the
# model default; it must not sort behind every numbered one.
DEFAULT_ORDER = 1


def _partner(row, person_id):
    """The other end of one row, or `None` when the row is about neither."""
    husband_id, wife_id = row[0], row[1]
    if husband_id == person_id:
        return wife_id
    if wife_id == person_id:
        return husband_id
    return None


def spouses_of(spouses, person_id):
    """Every partner id, unordered -- for "is this person my own spouse?"."""
    return set(
        partner for partner in (_partner(row, person_id) for row in spouses)
        if partner is not None
    )


def ranked_spouses_of(spouses, person_id):
    """`[(rank, spouse_id), ...]`, the marriage to answer through FIRST.

    The rule, stated once so nothing downstream has to guess it:

    1. A marriage that is not `goa` outranks one that is. A widow stays her
       late husband's family's thím, so `clan_spouse_pairs` keeps his row --
       but once she has remarried, "what do I call this person" is being
       asked about the family she is in now.
    2. Among equals, the lower `Marriage.order` wins: vợ cả before vợ lẽ.
       Polygamy is real in this data and the model already orders it.
    3. Only then the id, purely so the list is stable.

    THE ID IS THE TIE-BREAK, NEVER THE DECISION. `rank` is steps 1 and 2
    alone, so a caller can see when two candidates were separated by nothing
    but autoincrement order -- which is data-entry order, not a fact about
    the family. `kinship_affinal` hedges there instead of pretending. This
    whole function exists because the id used to BE the rule: it routed the
    wife of a younger brother through her late husband, the eldest, and told
    her to call her husband's elder brother `em`.
    """
    ranked = []
    for row in spouses:
        spouse_id = _partner(row, person_id)
        if spouse_id is None:
            continue
        status, order = row[2], row[3]
        rank = (1 if status == WIDOWED else 0,
                DEFAULT_ORDER if order is None else order)
        ranked.append((rank, spouse_id))
    ranked.sort()
    return ranked
