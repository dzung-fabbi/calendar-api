"""ORM writes for the personal family API.

Each function is ONE primitive write; the views compose them inside a single
`transaction.atomic()` per request after `services.family_rules` has approved
the change. Nothing here validates -- that split is what keeps the rules
testable without a database.

`updated_at` is bumped explicitly on queryset `update()` calls because
`auto_now` only fires on `Model.save()`.
"""

from django.db.models import Q
from django.utils import timezone

from giapha.models import FamilyPerson, FamilySpouse
from giapha.services.family_graph import canonical_pair


def create_person(family, draft):
    """`draft`: snake_case field dict from `services.family_draft.finalize_draft`."""
    return FamilyPerson.objects.create(family=family, **draft)


def apply_draft(person, draft):
    """Writes ONLY the draft fields (+ `updated_at`): a full `save()` would
    re-write `father_id`/`mother_id` from this stale instance and could undo
    a concurrent relation write."""
    for field, value in draft.items():
        setattr(person, field, value)
    person.save(update_fields=list(draft) + ['updated_at'])
    return person


def set_parent_slot(person_id, slot, parent_id, rel=None):
    """Write `father`/`mother` (+ its `_rel`). `parent_id=None` clears the
    slot. `rel` is stored only when `'adopted'` -- `'blood'` is the NULL
    default (spec §3.1)."""
    stored_rel = 'adopted' if (parent_id is not None and rel == 'adopted') else None
    FamilyPerson.objects.filter(id=person_id).update(**{
        slot + '_id': parent_id,
        slot + '_rel': stored_rel,
        'updated_at': timezone.now(),
    })


def upsert_spouse(family, a_id, b_id, spouse_type):
    """One row per unordered pair (spec §2.5: both directions in one write)."""
    low, high = canonical_pair(a_id, b_id)
    FamilySpouse.objects.update_or_create(
        person_a_id=low, person_b_id=high,
        defaults={'family': family, 'type': spouse_type},
    )
    FamilyPerson.objects.filter(id__in=(a_id, b_id)).update(updated_at=timezone.now())


def delete_spouse(a_id, b_id):
    low, high = canonical_pair(a_id, b_id)
    deleted, _ = FamilySpouse.objects.filter(person_a_id=low, person_b_id=high).delete()
    if deleted:
        FamilyPerson.objects.filter(id__in=(a_id, b_id)).update(updated_at=timezone.now())
    return bool(deleted)


def delete_person(person):
    """Spec §2.6 "xoá không lan": remove the row, detach every pointer to it,
    touch nothing else. Returns the ids that lost an edge (`detachedFrom`).

    The FKs already `SET_NULL`/`CASCADE` on their own; the explicit updates
    exist to (a) clear the `_rel` alongside the emptied slot and (b) bump
    `updated_at` on the detached rows so a client syncing by timestamp sees
    them change. `Family.self_person` is `SET_NULL` too, so "tôi" clears.
    """
    now = timezone.now()
    children = FamilyPerson.objects.filter(Q(father_id=person.id) | Q(mother_id=person.id))
    detached = set(children.values_list('id', flat=True))
    FamilyPerson.objects.filter(father_id=person.id).update(father_id=None, father_rel=None, updated_at=now)
    FamilyPerson.objects.filter(mother_id=person.id).update(mother_id=None, mother_rel=None, updated_at=now)

    links = FamilySpouse.objects.filter(Q(person_a_id=person.id) | Q(person_b_id=person.id))
    for a_id, b_id in links.values_list('person_a_id', 'person_b_id'):
        detached.add(b_id if a_id == person.id else a_id)
    links.delete()
    if detached:
        FamilyPerson.objects.filter(id__in=detached).update(updated_at=now)

    person.delete()
    return sorted(detached, key=str)


def set_self(family, person_id):
    family.self_person_id = person_id
    family.save(update_fields=['self_person', 'updated_at'])


def set_gio_event(person, event_id):
    person.gio_event_id = event_id or None
    person.save(update_fields=['gio_event_id', 'updated_at'])
    return person
