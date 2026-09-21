"""Editing a LINKED person from the personal tree (plan 260919 phase 5,
spec §14.5).

Private fields (time of birth/death, relationship, note, gioEventId, birth
order) are saved on the family person right away. Shared fields go to EACH
linked clan, independently:

    caller may write that person (`permissions_scope`) -> write through the
        clan write path, checking `clanVersions[clanId]` if given
        -> `applied` | `conflict` (with `current`) | `rejected` (rule error)
    otherwise -> an `update_person` change request -> `proposed`

One clan's conflict never blocks the private save or another clan.
Relationship mutations (`relations/*`) never reach a clan.
"""

import json

from django.db import transaction
from rest_framework import serializers

from giapha.models import ChangeRequest, FamilyPersonLink
from giapha.exceptions import BadRequestException
from giapha.permissions_scope import writable_ids_for_member
from giapha.selectors.clan import clan_member_for
from giapha.selectors.person_version import VersionConflict
from giapha.selectors.person_write import apply_person_update
from giapha.serializers.person import PersonReadSerializer, PersonWriteSerializer
from giapha.services.family_clan_field_map import SHARED_FAMILY_FIELDS, family_to_clan_payload
from giapha.services.person_rules import PersonValidationError
from giapha.views.change_request import submit_change_request


class ClanVersionsSerializer(serializers.Serializer):
    clanVersions = serializers.DictField(child=serializers.IntegerField(min_value=1), required=False, default=dict)

    def create(self, validated_data):
        raise NotImplementedError

    def update(self, instance, validated_data):
        raise NotImplementedError


def active_links_of(family, person_id):
    return list(
        FamilyPersonLink.objects.filter(
            family_id=family.id, family_person_id=person_id, clan__is_deleted=False,
            clan_person__is_deleted=False, clan__members__user_id=family.user_id,
        ).select_related('clan_person').order_by('id')
    )


def split_draft(draft):
    shared = {key: value for key, value in draft.items() if key in SHARED_FAMILY_FIELDS}
    private = {key: value for key, value in draft.items() if key not in SHARED_FAMILY_FIELDS}
    return shared, private


def _propose(user, link, payload):
    person = link.clan_person
    cr = ChangeRequest(
        clan_id=link.clan_id, proposer=user, action='update_person', target_person=person,
        payload_json=json.dumps(payload), base_updated_at=person.updated_at, base_version=person.version,
        proposer_note='Sửa từ gia phả cá nhân',
    )
    try:
        submit_change_request(cr, user)
    except BadRequestException as exc:
        return {'clanId': link.clan_id, 'result': 'rejected', 'message': str(exc.detail)}
    return {'clanId': link.clan_id, 'result': 'proposed', 'changeRequestId': cr.id}


def _write_one(user, link, payload, expected_version):
    person = link.clan_person
    serializer = PersonWriteSerializer(person, data=payload, partial=True)
    if not serializer.is_valid():
        return {'clanId': link.clan_id, 'result': 'rejected', 'errors': serializer.errors}

    scope = writable_ids_for_member(clan_member_for(user, link.clan_id), link.clan_id)
    if scope is not None and person.id not in scope:
        return _propose(user, link, payload)
    try:
        with transaction.atomic():
            apply_person_update(link.clan_id, person, serializer.validated_data, user,
                                expected_version=expected_version)
    except VersionConflict:
        person.refresh_from_db()
        return {'clanId': link.clan_id, 'result': 'conflict', 'current': PersonReadSerializer(person).data}
    except PersonValidationError as exc:
        return {'clanId': link.clan_id, 'result': 'rejected', 'message': str(exc)}
    return {'clanId': link.clan_id, 'result': 'applied', 'version': person.version}


def write_shared_to_clans(user, links, shared, clan_versions):
    """`clanWrites[]` -- one entry per linked clan (empty when no shared field changed)."""
    payload = family_to_clan_payload(shared)
    if not payload:
        return []
    return [_write_one(user, link, payload, clan_versions.get(str(link.clan_id))) for link in links]
