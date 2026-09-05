"""Assembling the answer for two people who share an ancestor.

Pure, and the bottom of the xưng-hô pipeline's assembly half: it owns the
response SHAPE (`result`) so that `kinship.py` and `kinship_affinal.py` build
the same dict rather than two dicts that drift apart.

Split out of `services/kinship.py` when the A-side marriage walk was added
and that file crossed 200 lines; `kinship_affinal` needs `blood_result` and
importing it back from `kinship` would be a cycle.
"""

from giapha.services.kinship_explain import explain_blood, explain_none
from giapha.services.kinship_lookup import gender_of, is_elder, name_of, resolve_term
from giapha.services.kinship_terms import BANG, TRUC

EMPTY_PATH = {'a_up': None, 'b_up': None, 'side': None}


def result(a_calls_b, b_calls_a, ancestor, path, explain):
    return {
        'a_calls_b': a_calls_b,
        'b_calls_a': b_calls_a,
        'common_ancestor': ancestor,
        'path': path,
        'explain': explain,
    }


def unrelated(reason):
    """"There is no link" -- HTTP 200, not an error (plan step 6).

    `confident` is True on purpose: we are certain there is no link. That is
    a finding, not the hedge that `confident: False` means everywhere else.

    Reached ONLY after both marriage walks came back empty. A marriage that
    WAS found but has no everyday word does not come here -- it hedges with
    `REASON_AFFINAL_NO_TERM` instead, because claiming "no relation" about a
    person's own stepmother is the confidently wrong answer this endpoint
    exists to avoid.
    """
    entry = {'term': None, 'confident': True, 'reason': reason}
    return result(dict(entry), dict(entry), None, dict(EMPTY_PATH), explain_none(reason))


def blood_result(by_id, index_a, index_b, found, a_id, b_id):
    """The answer for two people who share an ancestor.

    Each direction is resolved independently: `side` is taken from that
    person's own walk (B may be bên nội to A while A is bên ngoại to B), and
    the seniority flag is inverted with it.
    """
    ancestor_id, depth_a, depth_b, side_a = found
    side_b = index_b[ancestor_id][1]
    via_a = index_a[ancestor_id][2]
    via_b = index_b[ancestor_id][2]
    # Direct line exactly when one of the pair IS the common ancestor -- that
    # is what separates `con`/`cháu` from `cháu`/`chắt`.
    kind = TRUC if (depth_a == 0 or depth_b == 0) else BANG

    a_calls_b = resolve_term(
        kind, depth_a - depth_b, side_a, gender_of(by_id, b_id),
        is_elder(by_id, via_a, via_b),
    )
    b_calls_a = resolve_term(
        kind, depth_b - depth_a, side_b, gender_of(by_id, a_id),
        is_elder(by_id, via_b, via_a),
    )
    ancestor_name = name_of(by_id, ancestor_id)
    return result(
        a_calls_b, b_calls_a,
        {'id': ancestor_id, 'ho_ten': ancestor_name},
        {'a_up': depth_a, 'b_up': depth_b, 'side': side_a},
        explain_blood(
            name_of(by_id, a_id), name_of(by_id, b_id), a_calls_b, b_calls_a,
            ancestor_name, depth_a, depth_b, side_a,
        ),
    )
