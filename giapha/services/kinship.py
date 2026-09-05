"""Máy tính xưng hô -- "what do these two people call each other?".

Pure: no ORM, no `request`. Everything arrives as the plain dict rows
`selectors.person.clan_kinship_rows` returns plus, optionally, the
`(husband_id, wife_id, status, order)` rows from
`selectors.marriage.clan_spouse_pairs`. That is what lets
`tests/test_kinship.py` run on `SimpleTestCase`.

NORTHERN DIALECT (miền Bắc) IS THE MVP STANDARD. The vocabulary lives in
`kinship_terms.py` and nothing here is region-aware; Southern and Central
usage differs and is out of scope. See that module's docstring.

THE PIPELINE, ONE MODULE PER CONCERN
------------------------------------
    kinship_graph        -- walk up, find the common ancestor (which people)
    kinship_lookup       -- facts -> word                     (which word)
    kinship_terms        -- the blood vocabulary, data only
    kinship_affinal_terms-- the in-law vocabulary, data only
    kinship_marriage_rows-- which marriage to answer through
    kinship_explain      -- the human sentence
    kinship_blood        -- the answer for two blood relatives
    kinship_affinal      -- the answer through a marriage edge
    kinship              -- this file: pick which of the two applies

WHAT DECIDES THE WORD
---------------------
`gap = depth_a - depth_b` (generations B is above A) plus three facts:
nội vs ngoại, the seniority of the two branches at the common ancestor, and
-- only when there is no blood link at all -- a marriage edge. Any of the
three being unknown yields a hedge with `confident: False`, never a guess.
`parent_kind` (ruột/nuôi/kế) is deliberately ignored: an adopted child is
addressed exactly like a natural one, so distinguishing would be the
surprising behaviour.
"""

from giapha.services.kinship_affinal import affinal, married_couple, spouses_of
from giapha.services.kinship_blood import blood_result, unrelated
from giapha.services.kinship_graph import ancestor_index, best_common_ancestor
from giapha.services.kinship_terms import REASON_NO_BLOOD, REASON_SAME_PERSON


def resolve_kinship(rows, a_id, b_id, spouses=None):
    """The whole answer for one pair -- the only function views should call.

    `spouses` is optional so the caller can skip a query in the common case:
    an in-law term is only ever reachable when there is NO blood link, so the
    view loads marriages lazily and calls again with them.

    Marriage is walked from BOTH sides but only ONE hop deep. Two people who
    each married into the clan therefore come back `khong_cung_huyet_thong`.
    """
    by_id = {row['id']: row for row in rows}
    if a_id == b_id:
        # Same node, so there is no relationship to name. Returning "anh/em"
        # would be inventing a term; saying so plainly is the useful answer.
        return unrelated(REASON_SAME_PERSON)

    index_a = ancestor_index(rows, a_id)
    index_b = ancestor_index(rows, b_id)
    found = best_common_ancestor(index_a, index_b)
    if found is not None:
        return blood_result(by_id, index_a, index_b, found, a_id, b_id)

    if spouses:
        # BEFORE any of B's other marriages. `clan_spouse_pairs` keeps `goa`,
        # so a widow who remarried has both marriages on record; checking
        # this inside the loop answered "chị" for a man's own wife whenever
        # the late husband's id happened to sort lower. Being married to B
        # outranks every derived term, so no ranking is needed here.
        if a_id in spouses_of(spouses, b_id):
            return married_couple(by_id, a_id, b_id)
        answer = affinal(rows, by_id, index_a, index_b, a_id, b_id, spouses)
        if answer is not None:
            return answer
    return unrelated(REASON_NO_BLOOD)
