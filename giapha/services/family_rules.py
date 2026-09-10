"""Relationship invariants for the personal family API (spec §4).

Every function takes a `FamilyGraph` and ids, and either returns (possibly a
warning dict) or raises `FamilyRuleError`. No ORM: the views load the graph,
run these, then write. Order matters in each check -- the first failing rule
is the one the client sees, and tests pin that order.
"""

from giapha.services.family_graph import FATHER, MOTHER, gender_fits_slot, other_slot
from giapha.services.family_issue import MESSAGES, FamilyRuleError, not_found, warning

DANGLING_BY_SLOT = {'father': 'DANGLING_FATHER', 'mother': 'DANGLING_MOTHER'}


def require_person(graph, person_id):
    if person_id is None or not graph.has(person_id):
        raise not_found(person_id)


def check_set_parent(graph, child_id, slot, parent_id):
    """Spec §4.2 -- `parent_id` is not None here (clearing needs no check).
    Rejects self-parenting, a dangling parent id, a gender that does not fit
    the slot, and a parent who is already a descendant of the child (cycle).
    """
    if child_id == parent_id:
        raise FamilyRuleError('SELF_PARENT', person_id=child_id, other_id=parent_id)
    if not graph.has(parent_id):
        raise FamilyRuleError(DANGLING_BY_SLOT[slot], person_id=child_id, other_id=parent_id)
    if not gender_fits_slot(graph.gender(parent_id), slot):
        raise FamilyRuleError('GENDER_MISMATCH', person_id=child_id, other_id=parent_id)
    if parent_id in graph.descendants_of(child_id):
        raise FamilyRuleError('PARENT_CYCLE', person_id=child_id, other_id=parent_id)


def check_slot_free(graph, child_id, slot, parent_id):
    """`PARENT_SLOT_TAKEN` when the slot holds a DIFFERENT person. Re-setting
    the same parent is a no-op, not an error."""
    current = graph.parent_in_slot(child_id, slot)
    if current is not None and current != parent_id:
        message_key = 'PARENT_SLOT_TAKEN_FATHER' if slot == FATHER else 'PARENT_SLOT_TAKEN_MOTHER'
        raise FamilyRuleError(
            'PARENT_SLOT_TAKEN', message=MESSAGES[message_key], person_id=child_id, other_id=current,
        )


def check_link_spouse(graph, a_id, b_id):
    """Spec §4.4: only `SELF_SPOUSE` (and a missing person) block. Returns a
    `SPOUSE_IS_ANCESTOR` warning dict when the two are lineal, else `None`."""
    if a_id == b_id:
        raise FamilyRuleError('SELF_SPOUSE', person_id=a_id, other_id=b_id)
    if not graph.has(b_id):
        raise FamilyRuleError('DANGLING_SPOUSE', person_id=a_id, other_id=b_id)
    if graph.is_lineal(a_id, b_id):
        return warning('SPOUSE_IS_ANCESTOR', person_id=a_id, other_id=b_id)
    return None


def other_parent_candidates(graph, parent_id, child_id, slot):
    """Spec §4.6: who may fill `slot` on `child_id` once `parent_id` holds the
    other slot -- `getPartners(parent)` filtered to those whose gender fits,
    who are not the child, and who would not close a cycle. Sorted by string
    id so "exactly one candidate" is deterministic in tests."""
    descendant_ids = graph.descendants_of(child_id)
    return sorted(
        (
            pid for pid in graph.partners_of(parent_id)
            if pid != child_id and gender_fits_slot(graph.gender(pid), slot) and pid not in descendant_ids
        ),
        key=str,
    )


def pick_other_parent(candidates, requested_id):
    """Spec §4.6 fill rule: the requested id if it is a candidate; else the
    single candidate if there is exactly one; else nobody (never guess)."""
    if requested_id is not None:
        return requested_id if requested_id in candidates else None
    return candidates[0] if len(candidates) == 1 else None


def first_spouse_fill_targets(graph, person_id, partner_id):
    """Spec §4.4 side effect: when `person_id` gains their FIRST explicit
    spouse, fill the empty other-parent slot of each of their children with
    `partner_id` -- if the gender fits and it closes no cycle. Returns
    `[(child_id, slot), ...]`; empty when `person_id` already had a spouse
    ("từ người thứ hai trở đi không đoán")."""
    if graph.spouses_of(person_id):
        return []
    targets = []
    partner_gender = graph.gender(partner_id)
    for child_id in graph.children_of(person_id):
        held = FATHER if graph.parent_in_slot(child_id, FATHER) == person_id else MOTHER
        empty = other_slot(held)
        if graph.parent_in_slot(child_id, empty) is not None:
            continue
        if child_id == partner_id or not gender_fits_slot(partner_gender, empty):
            continue
        if partner_id in graph.descendants_of(child_id):
            continue
        targets.append((child_id, empty))
    return targets


def check_family_capacity(graph, max_persons):
    """Every request loads the whole tree (spec §1: < 500 people); the cap
    keeps that assumption honest. Zero extra queries -- the graph is loaded."""
    if len(graph.persons) >= max_persons:
        raise FamilyRuleError('FAMILY_FULL', message=MESSAGES['FAMILY_FULL'].format(max_persons))


def check_add_relative(graph, anchor_id, kind, new_gender):
    """Spec §4.7 pre-creation gates, run BEFORE the new row exists so a
    rejected request never leaves an orphan behind."""
    require_person(graph, anchor_id)
    if kind in ('father', 'mother'):
        check_slot_free(graph, anchor_id, kind, None)
        if not gender_fits_slot(new_gender, kind):
            raise FamilyRuleError('GENDER_MISMATCH', person_id=anchor_id)
    elif kind == 'sibling' and not graph.has_any_parent(anchor_id):
        raise FamilyRuleError('NO_PARENT_FOR_SIBLING', person_id=anchor_id)
