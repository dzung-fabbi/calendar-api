"""`POST /v1/family/links/contribute` -- "đóng góp" a personal-tree person
to a clan (plan 260919 phase 4).

The new clan person is built from the family person's SHARED fields
(`services.family_clan_field_map`) under the given clan parents. If the
caller may write there (`permissions_scope`: editor+, or a verified member
whose family scope holds one of the parents) it is created at once and
linked (`result: applied`). Otherwise it becomes a `create_person` change
request carrying `family_person`; approving it links automatically
(`views.change_request_review`) -- `result: proposed`.
"""

import json

from django.db import transaction
from rest_framework import serializers as drf_serializers
from rest_framework.response import Response

from giapha.models import ChangeRequest
from giapha.exceptions import BadRequestException
from giapha.permissions_scope import writable_ids_for_member
from giapha.selectors.family import get_person_or_none
from giapha.selectors.family_link import clan_person_rows, links_in_clan
from giapha.selectors.family_link_write import create_links
from giapha.selectors.person_write import apply_person_create_many
from giapha.serializers.change_request import validated_payload
from giapha.serializers.family_link import LinkContributeSerializer
from giapha.services.family_clan_field_map import SHARED_FAMILY_FIELDS, family_to_clan_payload
from giapha.services.family_issue import FamilyRuleError, not_found
from giapha.services.person_rules import PersonValidationError
from giapha.views.family_base import FamilyAPIView
from giapha.views.change_request import submit_change_request
from giapha.views.family_link import require_member


def contribute_payload(family_person, father_id, mother_id):
    payload = family_to_clan_payload({field: getattr(family_person, field) for field in SHARED_FAMILY_FIELDS})
    payload.update({'father_id': father_id, 'mother_id': mother_id})
    return payload


def _in_scope(scope, parent_ids):
    return scope is None or any(pid in scope for pid in parent_ids if pid is not None)


def propose_contribution(user, clan_id, family_person, payload, note):
    cr = ChangeRequest(
        clan_id=clan_id, proposer=user, action='create_person', family_person=family_person,
        payload_json=json.dumps(payload), proposer_note=note,
    )
    try:
        return submit_change_request(cr, user)
    except BadRequestException as exc:
        raise FamilyRuleError('VALIDATION', message=str(exc.detail))


def contribute_person(user, family, family_person, clan_id, parents, note=''):
    """Shared by this endpoint and `add-relative` `contributeTo` (phase 5).
    Returns `{clanId, result: applied|proposed, clanPersonId|changeRequestId}`;
    raises `FamilyRuleError` for anything the caller must report."""
    member = require_member(user, clan_id)
    if family_person.id in links_in_clan(family, clan_id):
        raise FamilyRuleError('LINK_CONFLICT', person_id=family_person.id)
    live = {row['id'] for row in clan_person_rows(clan_id)}
    for pid in parents:
        if pid is not None and pid not in live:
            raise FamilyRuleError('CLAN_PERSON_NOT_FOUND', other_id=pid, status=404)

    payload = contribute_payload(family_person, *parents)
    try:
        data = validated_payload('create_person', payload)
    except drf_serializers.ValidationError as exc:
        raise FamilyRuleError('VALIDATION', extra={'fields': exc.detail})

    if not _in_scope(writable_ids_for_member(member, clan_id), parents):
        cr = propose_contribution(user, clan_id, family_person, payload, note)
        return {'clanId': clan_id, 'result': 'proposed', 'changeRequestId': cr.id}

    with transaction.atomic():
        try:
            clan_person = apply_person_create_many(clan_id, [data], user)[0]
        except PersonValidationError as exc:
            raise FamilyRuleError('VALIDATION', message=str(exc))
        if not create_links(family, clan_id, [(family_person.id, clan_person.id)], user):
            raise FamilyRuleError('LINK_CONFLICT', person_id=family_person.id)
    return {'clanId': clan_id, 'result': 'applied', 'clanPersonId': clan_person.id}


class FamilyLinkContributeAPIView(FamilyAPIView):
    def post(self, request):
        body = self.validate(LinkContributeSerializer, request.data)
        family_person = get_person_or_none(self.family.id, body['personId'])
        if family_person is None:
            raise not_found(body['personId'])
        result = contribute_person(
            request.user, self.family, family_person, body['clanId'],
            [body['fatherClanPersonId'], body['motherClanPersonId']], body['note'],
        )
        status = 201 if result['result'] == 'applied' else 202
        return Response(dict(result, ok=True), status=status)
