"""Who a member may edit directly -- pure, no ORM.

"Phạm vi gia đình" of person P (plan 260919 phase 1):

    {P} ∪ spouses(P) ∪ parents(P) ∪ descendants(P) ∪ spouses(descendants)
        ∪ full/half siblings of P that nobody has claimed-and-verified yet

Siblings are the one conditional group: once a sibling is in the app and
verified, only they (and approvers) edit their node. The sibling rule does
NOT spread to a sibling's spouse or children.

"Phạm vi chi" (phase 6) of a branch root R is R ∪ descendants(R) ∪ their
spouses -- the same walk minus parents/siblings.

Inputs are the plain shapes the selectors return:
`parent_edges = [(id, father_id, mother_id), ...]` and
`marriage_pairs = [(husband_id, wife_id), ...]`. Descendants reuse
`services.tree.subtree_ids`, which is cycle-safe on corrupt admin data.
"""

from giapha.services.tree import subtree_ids


def _spouses_of(marriage_pairs):
    """`{person_id: {spouse_id, ...}}`, both directions."""
    spouses = {}
    for husband_id, wife_id in marriage_pairs:
        spouses.setdefault(husband_id, set()).add(wife_id)
        spouses.setdefault(wife_id, set()).add(husband_id)
    return spouses


def _with_spouses(person_ids, spouses):
    result = set(person_ids)
    for person_id in person_ids:
        result |= spouses.get(person_id, set())
    return result


def branch_scope_ids(parent_edges, marriage_pairs, root_id):
    """Branch root + every descendant + their spouses. Empty when the root is
    not in `parent_edges` (e.g. soft-deleted and filtered out upstream).
    """
    known_ids = {row[0] for row in parent_edges}
    if root_id not in known_ids:
        return set()
    return _with_spouses(subtree_ids(parent_edges, root_id), _spouses_of(marriage_pairs))


def family_scope_ids(parent_edges, marriage_pairs, person_id, verified_person_ids):
    """Set of person ids inside P's family scope (see module docstring).

    `verified_person_ids`: nodes currently bound to a member with
    `person_verified=True` -- used only to drop siblings who can speak for
    themselves. Returns an empty set when `person_id` is not a live node.
    """
    parents_of = {row[0]: (row[1], row[2]) for row in parent_edges}
    if person_id not in parents_of:
        return set()

    spouses = _spouses_of(marriage_pairs)
    scope = _with_spouses(subtree_ids(parent_edges, person_id), spouses)

    own_parents = {pid for pid in parents_of[person_id] if pid is not None and pid in parents_of}
    scope |= own_parents

    for other_id, (father_id, mother_id) in parents_of.items():
        if other_id == person_id or other_id in verified_person_ids:
            continue
        if father_id in own_parents or mother_id in own_parents:
            scope.add(other_id)
    return scope
