"""Write an `ImportPlan` (`services.family_import`) in one transaction with a
FIXED number of queries, whatever the family size:

    1 bulk INSERT persons (no edges yet -- a child row may precede its parent)
    1 bulk UPDATE edges + the client's createdAt/updatedAt
      (`auto_now_add`/`auto_now` would overwrite them on insert; `bulk_update`
      does not run `pre_save`, so the client values stick)
    1 bulk INSERT spouse links
    1 UPDATE family (import_key, self)

Ids are generated here (uuid4) before the insert, which is what lets edges be
resolved in memory instead of re-reading the rows.
"""

import uuid

from django.utils import timezone

from giapha.models import FamilyPerson, FamilySpouse


def import_id_map(family_id):
    """`{legacy_id: str(uuid)}` of an already-imported family (idempotent replay)."""
    rows = FamilyPerson.objects.filter(family_id=family_id, legacy_id__isnull=False).values_list('legacy_id', 'id')
    return {legacy_id: str(person_id) for legacy_id, person_id in rows}


def write_import(family, plan, import_key):
    """Caller wraps this in `transaction.atomic()` with the Family row locked."""
    now = timezone.now()
    id_map = {client_id: uuid.uuid4() for client_id, _fields in plan.persons}

    persons, stamps = [], {}
    for client_id, fields in plan.persons:
        row = dict(fields)
        created_at = row.pop('created_at') or now
        stamps[client_id] = (created_at, row.pop('updated_at') or created_at)
        persons.append(FamilyPerson(id=id_map[client_id], family=family, legacy_id=client_id, **row))
    # `pre_save` of auto_now(_add) overwrites the instance attributes here...
    FamilyPerson.objects.bulk_create(persons)
    # ...so the client timestamps are put back afterwards for the bulk_update.
    for person in persons:
        person.created_at, person.updated_at = stamps[person.legacy_id]

    by_client_id = {person.legacy_id: person for person in persons}
    for child_id, slot, parent_id, rel in plan.parents:
        child = by_client_id[child_id]
        setattr(child, slot + '_id', id_map[parent_id])
        setattr(child, slot + '_rel', rel)
    if persons:
        FamilyPerson.objects.bulk_update(
            persons, ['father', 'mother', 'father_rel', 'mother_rel', 'created_at', 'updated_at'],
        )

    FamilySpouse.objects.bulk_create([
        FamilySpouse(family=family, person_a_id=id_map[a], person_b_id=id_map[b], type=spouse_type)
        for a, b, spouse_type in plan.spouses
    ])

    family.import_key = import_key
    family.self_person_id = id_map[plan.self_id] if plan.self_id else None
    family.save(update_fields=['import_key', 'self_person', 'updated_at'])
    return {client_id: str(person_id) for client_id, person_id in id_map.items()}
