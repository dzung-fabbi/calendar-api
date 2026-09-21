"""The ONE write path for clan persons: create, update, soft-delete.

Called by the person views AND by change-request approval (plan 260919
phase 2), so a proposal applied by a reviewer goes through exactly the same
rules, revision recording and generation recompute as a direct edit.

Lives in `selectors/` (not `services/`) because it writes through the ORM --
same reason as `selectors/revision.record` and `selectors/family_write`.
Every function raises `PersonValidationError` on a rule violation; callers
turn it into a 400. Callers own permission checks.
"""

from django.conf import settings
from django.db import transaction

from giapha.models import Person
from giapha.selectors.family_link_detach import detach_for_clan_person
from giapha.selectors.person_version import lock_and_bump
from giapha.selectors.person import active_person_count, birth_solar_by_id, children_count, clan_edges
from giapha.selectors.revision import record
from giapha.selectors.tree import recompute_descendant_generations
from giapha.services.person_rules import PersonValidationError, ids_from_edges, validate_person_write
from giapha.services.tree import compute_generations

# The fields `validate_person_write` cares about; used to build the "merged
# current + incoming" payload for a partial update.
RULE_FIELDS = ('father_id', 'mother_id', 'birth_solar', 'death_solar', 'death_lunar_day', 'death_lunar_month')
# `father_id`/`mother_id` changing is what triggers the descendant-subtree
# generation recompute after an update.
_PARENT_FIELDS = ('father_id', 'mother_id')


def apply_person_update(clan_id, person, data, actor, force=False, change_request=None, expected_version=None):
    """Validate `data` (serializer `validated_data`, partial) against the
    current tree and save it onto `person`, recording a revision first.
    `expected_version` (optional): raise `VersionConflict` unless the row is
    still at that version -- omitted means "no check" (older clients).
    """
    edges = clan_edges(clan_id)
    merged = {field: getattr(person, field) for field in RULE_FIELDS}
    merged.update({key: value for key, value in data.items() if key in RULE_FIELDS})
    validate_person_write(
        merged, edges=edges, ids_in_clan=ids_from_edges(edges),
        birth_map=birth_solar_by_id(clan_id), existing_count=0,
        max_persons=settings.MAX_CLAN_PERSONS, force=force, person_id=person.id,
    )
    parent_changed = any(field in data and data[field] != getattr(person, field) for field in _PARENT_FIELDS)

    with transaction.atomic():
        lock_and_bump(person, expected_version)
        record(person, actor=actor, action='update', change_request=change_request)
        for field, value in data.items():
            setattr(person, field, value)
        person.save()
        if parent_changed:
            # Only the descendant subtree, not the whole clan -- see
            # `selectors.tree.recompute_descendant_generations`.
            recompute_descendant_generations(clan_id, person.id)
            person.refresh_from_db(fields=['generation'])
    return person


def apply_person_create_many(clan_id, items, actor, force=False, change_request=None):
    """Create every item (serializer `validated_data` dicts) in one
    transaction. `clan_edges`/`birth_solar_by_id` are loaded ONCE and updated
    in memory as the batch is walked, so validating item N costs no query.
    Returns the created persons re-fetched with parents joined (creation order).
    """
    edges = clan_edges(clan_id)
    ids_in_clan = ids_from_edges(edges)
    birth_map = birth_solar_by_id(clan_id)
    person_count = active_person_count(clan_id)

    created = []
    with transaction.atomic():
        for item in items:
            validate_person_write(
                item, edges=edges, ids_in_clan=ids_in_clan, birth_map=birth_map,
                existing_count=person_count, max_persons=settings.MAX_CLAN_PERSONS,
                force=force, person_id=None,
            )
            person = Person.objects.create(clan_id=clan_id, **item)
            record(person, actor=actor, action='create', change_request=change_request)

            edges.append((person.id, item.get('father_id'), item.get('mother_id')))
            ids_in_clan.add(person.id)
            birth_map[person.id] = item.get('birth_solar')
            person_count += 1
            created.append(person)

        # `generation` is derived state: compute it over the FULL updated
        # edge set -- a new row can be the parent of a later row in the batch.
        generations = compute_generations(edges)
        for person in created:
            person.generation = generations.get(person.id)
        Person.objects.bulk_update(created, ['generation'])

    # Re-fetch so `father`/`mother` are joined: the in-memory instances have
    # empty relation caches and the read serializer would N+1 on them.
    return list(
        Person.objects.filter(id__in=[person.id for person in created])
        .select_related('father', 'mother')
        .order_by('id')
    )


def apply_person_delete(person, actor, change_request=None):
    """Soft-delete. Refused while any person (live or soft-deleted) still
    references `person` as a parent -- restoring such a child later would
    point it at a node no live view shows.
    """
    blocking = children_count(person.id)
    if blocking:
        raise PersonValidationError(
            'Không thể xoá vì còn {} người con đang tham chiếu người này làm cha/mẹ.'.format(blocking)
        )
    with transaction.atomic():
        lock_and_bump(person)
        record(person, actor=actor, action='delete', change_request=change_request)
        person.is_deleted = True
        person.save(update_fields=['is_deleted', 'version', 'updated_at'])
        # Personal trees linked to this node keep its last values (snapshot).
        detach_for_clan_person(person.id)
