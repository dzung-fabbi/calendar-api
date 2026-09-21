"""`POST /clans/{clan_id}/invites/{invite_id}/approve` and `/reject`.

Owner or manager (`IsClanApprover`); an invite granting `editor` is owner-only
(a manager may not hand out edit rights over the whole clan). Approving mints
the code -- until then the invite has none, so nothing redeemable ever
existed for a request nobody approved. The inviter gets a push either way.
"""

from django.db import transaction
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.notifications import push_to_users
from giapha.permissions import IsClanApprover, cached_member
from giapha.selectors.invite import get_invite_for_review
from giapha.serializers.clan_invite import ClanInviteSerializer, ReviewNoteSerializer
from giapha.services.invite_policy import STATUS_ACTIVE, STATUS_PENDING
from giapha.views.clan_invite import INVITE_NOT_FOUND, save_with_fresh_code

NOT_PENDING_DETAIL = 'Lời mời này không ở trạng thái chờ duyệt.'
EDITOR_INVITE_OWNER_ONLY = 'Chỉ trưởng họ mới duyệt được lời mời quyền biên tập.'
STATUS_REJECTED = 'rejected'


def _pending_invite_or_error(request, clan_id, invite_id):
    invite = get_invite_for_review(clan_id, invite_id)
    if invite is None:
        raise NotFound(INVITE_NOT_FOUND)
    if invite.status != STATUS_PENDING:
        raise BadRequestException(NOT_PENDING_DETAIL)
    if invite.role != 'viewer' and cached_member(request, clan_id).role != 'owner':
        raise PermissionDenied(EDITOR_INVITE_OWNER_ONLY)
    return invite


def _note(request):
    serializer = ReviewNoteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data['note']


class ClanInviteApproveAPIView(APIView):
    permission_classes = [IsAuthenticated, IsClanApprover]

    def post(self, request, clan_id, invite_id):
        note = _note(request)
        with transaction.atomic():
            invite = _pending_invite_or_error(request, clan_id, invite_id)
            invite.status = STATUS_ACTIVE
            invite.approved_by = request.user
            invite.review_note = note
            save_with_fresh_code(invite)
        push_to_users(
            [invite.created_by_id], 'Lời mời đã được duyệt',
            'Lời mời của bạn đã được duyệt, mã mời: {}.'.format(invite.code),
            {'type': 'invite_approved', 'clan_id': clan_id, 'invite_id': invite.id},
        )
        return Response({'data': ClanInviteSerializer(invite).data})


class ClanInviteRejectAPIView(APIView):
    permission_classes = [IsAuthenticated, IsClanApprover]

    def post(self, request, clan_id, invite_id):
        note = _note(request)
        with transaction.atomic():
            invite = _pending_invite_or_error(request, clan_id, invite_id)
            invite.status = STATUS_REJECTED
            invite.approved_by = request.user
            invite.review_note = note
            invite.save(update_fields=['status', 'approved_by', 'review_note'])
        push_to_users(
            [invite.created_by_id], 'Lời mời bị từ chối',
            'Lời mời của bạn không được duyệt.' + (' Lý do: {}'.format(note) if note else ''),
            {'type': 'invite_rejected', 'clan_id': clan_id, 'invite_id': invite.id},
        )
        return Response({'data': ClanInviteSerializer(invite).data})
