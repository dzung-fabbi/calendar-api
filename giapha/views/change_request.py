"""`/clans/{clan_id}/change-requests` -- propose, list, read, withdraw.

Any member may propose (the point is editing OUTSIDE one's own scope).
Reviewers (editor+, see `change_request_review.can_review`) list every
proposal they can act on; everyone else only ever sees their own -- another
member's proposal is a 404, like any row the caller may not read.
Review actions live in `views/change_request_review.py`.
"""

import json

from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.models import ChangeRequest
from giapha.notifications import push_to_users
from giapha.permissions import EDITOR_ROLES, IsClanMember, cached_member
from giapha.selectors.change_request import (
    MAX_PENDING_PER_PROPOSER,
    change_requests_of,
    get_change_request,
    get_change_request_for_update,
    pending_count_for,
)
from giapha.selectors.change_request_apply import live_target_marriage, live_target_person
from giapha.serializers.change_request import ChangeRequestCreateSerializer, ChangeRequestSerializer, validated_payload
from giapha.views.change_request_review import can_review, current_state, reviewer_user_ids

CR_NOT_FOUND = 'Không tìm thấy đề xuất.'
TARGET_NOT_FOUND = 'Không tìm thấy người hoặc hôn nhân cần sửa.'
TOO_MANY_PENDING = 'Bạn đang có {} đề xuất chờ duyệt. Hãy chờ duyệt bớt trước khi gửi thêm.'
WITHDRAW_FORBIDDEN = 'Chỉ người gửi mới rút được đề xuất đang chờ duyệt.'
MAX_LIST = 200


def submit_change_request(cr, user):
    """Save a new proposal (pending cap per proposer) and push its reviewers.
    The ONE entry point for every proposal source -- `/change-requests`,
    linked-person edits, contributions (review M3)."""
    if pending_count_for(cr.clan_id, user.id) >= MAX_PENDING_PER_PROPOSER:
        raise BadRequestException(TOO_MANY_PENDING.format(MAX_PENDING_PER_PROPOSER))
    cr.save()
    push_to_users(
        [uid for uid in reviewer_user_ids(cr.clan_id, cr) if uid != user.id],
        'Đề xuất sửa gia phả', 'Có đề xuất thay đổi gia phả đang chờ bạn duyệt.',
        {'type': 'change_request_pending', 'clan_id': cr.clan_id, 'change_request_id': cr.id},
    )
    return cr


def visible_change_request(request, clan_id, cr_id):
    cr = get_change_request(clan_id, cr_id)
    if cr is None or (cr.proposer_id != request.user.id and not can_review(request, clan_id, cr)):
        raise NotFound(CR_NOT_FOUND)
    return cr


class ChangeRequestListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsClanMember]

    def get(self, request, clan_id):
        mine_only = request.query_params.get('mine') in ('1', 'true')
        is_reviewer = cached_member(request, clan_id).role in EDITOR_ROLES
        proposer_id = request.user.id if (mine_only or not is_reviewer) else None
        # Default `pending`: the queue, not the clan's whole history (review M2).
        status_filter = request.query_params.get('status', 'pending')
        rows = change_requests_of(clan_id, status=status_filter, proposer_id=proposer_id)[:MAX_LIST]
        if proposer_id is None:
            rows = [cr for cr in rows if can_review(request, clan_id, cr)]
        return Response({'data': ChangeRequestSerializer(rows, many=True).data})

    def post(self, request, clan_id):
        serializer = ChangeRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data
        action = body['action']

        cr = ChangeRequest(clan_id=clan_id, proposer=request.user, action=action, proposer_note=body['note'])
        instance = None
        if body['target_person_id'] is not None and action in ('update_person', 'delete_person'):
            cr.target_person_id = body['target_person_id']
            instance = live_target_person(cr)
            if instance is None:
                raise BadRequestException(TARGET_NOT_FOUND)
            cr.base_updated_at = instance.updated_at
            cr.base_version = instance.version
        elif body['target_marriage_id'] is not None and action in ('update_marriage', 'delete_marriage'):
            cr.target_marriage_id = body['target_marriage_id']
            instance = live_target_marriage(cr)
            if instance is None:
                raise BadRequestException(TARGET_NOT_FOUND)

        data = validated_payload(action, body['payload'], instance=instance)
        cr.payload_json = json.dumps({key: body['payload'][key] for key in data if key in body['payload']})

        submit_change_request(cr, request.user)
        return Response({'data': ChangeRequestSerializer(cr).data}, status=status.HTTP_201_CREATED)


class ChangeRequestDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsClanMember]

    def get(self, request, clan_id, cr_id):
        cr = visible_change_request(request, clan_id, cr_id)
        data = ChangeRequestSerializer(cr).data
        data['current'] = current_state(cr)
        return Response({'data': data})

    def delete(self, request, clan_id, cr_id):
        visible_change_request(request, clan_id, cr_id)
        with transaction.atomic():
            cr = get_change_request_for_update(clan_id, cr_id)
            if cr.proposer_id != request.user.id or cr.status != 'pending':
                raise PermissionDenied(WITHDRAW_FORBIDDEN)
            cr.status = 'withdrawn'
            cr.save(update_fields=['status'])
        return Response(status=status.HTTP_204_NO_CONTENT)
