"""The relationship mutations of spec §4, composed from `services.family_rules`
(decide) and `selectors.family_write` (write).

Every function takes the request's loaded `FamilyGraph` and KEEPS IT IN SYNC
with what it just wrote, so a later step in the same request (e.g. the
fill-other-parent side effect after `link_child`) reasons about the tree as it
now is, without a reload. Callers wrap a whole request in one
`transaction.atomic()`; nothing here opens its own except `auto_link_by_label`,
which must not undo the person it is trying to link.

Functions that may produce a non-blocking issue return the warning dict (or
`None`); the view puts it in the envelope's `warning`.
"""

from django.conf import settings
from django.db import transaction

from giapha.selectors import family_write as writes
from giapha.services import family_rules as rules
from giapha.services.family_graph import FATHER, MOTHER, SLOTS, other_slot, slot_for_parent_gender
from giapha.services.family_issue import FamilyRuleError, warning
from giapha.services.family_labels import plan_link


def set_parent(graph, child_id, slot, parent_id, rel='blood'):
    """Spec §4.2/§4.3. `parent_id=None` clears. An explicit set REPLACES the
    current occupant (that is how the edit form changes a parent); the
    no-overwrite rule belongs to `link_child`/`add_relative`."""
    rules.require_person(graph, child_id)
    if parent_id is not None:
        rules.check_set_parent(graph, child_id, slot, parent_id)
    writes.set_parent_slot(child_id, slot, parent_id, rel)
    graph.set_parent(child_id, slot, parent_id)


def link_spouse(family, graph, a_id, b_id, spouse_type='married'):
    """Spec §4.4. Returns the `SPOUSE_IS_ANCESTOR` warning or `None`. Fill
    targets are computed BEFORE the link is recorded -- "first spouse" is a
    statement about the tree as it was."""
    rules.require_person(graph, a_id)
    issue = rules.check_link_spouse(graph, a_id, b_id)
    fills = [(child, slot, b_id) for child, slot in rules.first_spouse_fill_targets(graph, a_id, b_id)]
    fills += [(child, slot, a_id) for child, slot in rules.first_spouse_fill_targets(graph, b_id, a_id)]

    writes.upsert_spouse(family, a_id, b_id, spouse_type)
    graph.add_spouse(a_id, b_id, spouse_type)
    for child_id, slot, parent_id in fills:
        writes.set_parent_slot(child_id, slot, parent_id)
        graph.set_parent(child_id, slot, parent_id)
    return issue


def unlink_spouse(graph, a_id, b_id):
    """Spec §4.5 -- the single stored row IS both directions."""
    rules.require_person(graph, a_id)
    rules.require_person(graph, b_id)
    writes.delete_spouse(a_id, b_id)


def link_child(graph, parent_id, child_id, other_parent_id=None):
    """Spec §4.6. The parent's gender picks the slot; an occupied slot is
    `PARENT_SLOT_TAKEN`, never overwritten; then the other slot is filled
    from the parent's partners when that is unambiguous. Returns a warning
    when the caller named an `other_parent_id` that was not a candidate."""
    rules.require_person(graph, parent_id)
    rules.require_person(graph, child_id)
    slot = slot_for_parent_gender(graph.gender(parent_id))
    rules.check_set_parent(graph, child_id, slot, parent_id)
    rules.check_slot_free(graph, child_id, slot, parent_id)
    writes.set_parent_slot(child_id, slot, parent_id)
    graph.set_parent(child_id, slot, parent_id)
    return fill_other_parent(graph, parent_id, child_id, other_parent_id)


def fill_other_parent(graph, parent_id, child_id, other_parent_id=None):
    """Fills the empty slot when spec §4.6 allows it. Returns `None`, or an
    `OTHER_PARENT_NOT_CANDIDATE` warning when a requested id was ignored --
    the spec says not to fill in that case, but silently dropping the
    client's choice would hide a client bug."""
    held = FATHER if graph.parent_in_slot(child_id, FATHER) == parent_id else MOTHER
    empty = other_slot(held)
    if graph.parent_in_slot(child_id, empty) is not None:
        return None
    candidates = rules.other_parent_candidates(graph, parent_id, child_id, empty)
    picked = rules.pick_other_parent(candidates, other_parent_id)
    if picked is None:
        if other_parent_id is not None:
            return warning('OTHER_PARENT_NOT_CANDIDATE', person_id=child_id, other_id=other_parent_id)
        return None
    writes.set_parent_slot(child_id, empty, picked)
    graph.set_parent(child_id, empty, picked)
    return None


def copy_parents(graph, from_id, to_id):
    """Sibling = same father and mother (spec §4.7/§4.8). Copies ids only;
    `_rel` stays NULL (blood) for the new person."""
    for slot in SLOTS:
        parent_id = graph.parent_in_slot(from_id, slot)
        if parent_id is not None:
            writes.set_parent_slot(to_id, slot, parent_id)
            graph.set_parent(to_id, slot, parent_id)


def create_person(family, graph, draft):
    """The one creation path: capacity gate, INSERT, index update."""
    rules.check_family_capacity(graph, settings.FAMILY_MAX_PERSONS)
    person = writes.create_person(family, draft)
    graph.add_person({'id': person.id, 'gender': person.gender})
    return person


def add_relative(family, graph, anchor_id, kind, draft, other_parent_id=None):
    """Spec §4.7: gate, THEN create, THEN link -- a rejected request must not
    leave an orphan. Returns `(new_person_id, warning)`."""
    rules.check_add_relative(graph, anchor_id, kind, draft.get('gender', 'unknown'))
    person = create_person(family, graph, draft)

    issue = None
    if kind in (FATHER, MOTHER):
        set_parent(graph, anchor_id, kind, person.id)
    elif kind == 'spouse':
        issue = link_spouse(family, graph, anchor_id, person.id)
    elif kind == 'child':
        issue = link_child(graph, anchor_id, person.id, other_parent_id)
    elif kind == 'sibling':
        copy_parents(graph, anchor_id, person.id)
    return person.id, issue


def auto_link_by_label(family, graph, new_id, label):
    """Spec §4.8 for `POST /persons`: link the just-created standalone person
    by their "Quan hệ với bạn" label when it names exactly one edge. Never
    blocks the save -- a rule failure while linking rolls back only the link
    (savepoint) and comes back as the `hint`. Returns `(linked, hint)`."""
    plan, hint = plan_link(graph, family.self_person_id, label, graph.gender(new_id))
    if plan is None:
        return False, hint
    self_id = family.self_person_id
    try:
        with transaction.atomic():
            if plan[0] == 'set_parent':
                set_parent(graph, plan[1], plan[2], new_id)
            elif plan[0] == 'spouse':
                link_spouse(family, graph, self_id, new_id)
            elif plan[0] == 'child':
                link_child(graph, self_id, new_id)
            elif plan[0] == 'sibling':
                copy_parents(graph, self_id, new_id)
    except FamilyRuleError as exc:
        return False, exc.message
    return True, None
