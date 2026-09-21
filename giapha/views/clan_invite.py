"""Invite issuing, listing and revocation (`/clans/{clan_id}/invites`).

Since plan 260919 phase 1 any member may ask for an invite, not only the
owner. `services.invite_policy` decides whether it is `active` at once (a
code is minted) or `pending_approval` (no code until an approver approves it
in `views/invite_review.py`). A plain viewer must have a VERIFIED binding to
invite anyone -- an unverified claim is not a basis for vouching for people.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.models import ClanInvite
from giapha.notifications import push_to_users
from giapha.permissions import APPROVER_ROLES, EDITOR_ROLES, IsClanMember, cached_member
from giapha.permissions_scope import invite_scope_ids
from giapha.selectors.clan import approver_user_ids, get_invite_by_id, invites_of
from giapha.selectors.invite import invites_created_by, open_invite_count, person_is_claimed
from giapha.selectors.person import get_person_or_none
from giapha.serializers.clan_invite import ClanInviteCreateSerializer, ClanInviteSerializer
from giapha.services.invite_code import generate_code
from giapha.services.invite_policy import STATUS_ACTIVE, invite_initial_status
from giapha.views.member_binding import PERSON_CLAIMED, PERSON_DECEASED, PERSON_OTHER_CLAN, _is_deceased

INVITE_NOT_FOUND = 'Không tìm thấy mã mời.'
NOT_VERIFIED_DETAIL = 'Bạn cần được xác minh là một người trong cây trước khi mời người khác.'
DELETE_FORBIDDEN_DETAIL = 'Chỉ người tạo hoặc trưởng họ mới thu hồi được mã mời này.'
TOO_MANY_OPEN_DETAIL = 'Bạn đang có tối đa {} lời mời chưa dùng. Hãy thu hồi bớt trước khi mời thêm.'
MAX_CODE_ATTEMPTS = 5
MAX_OPEN_INVITES_PER_MEMBER = 10


class MemberInviteThrottle(ScopedRateThrottle):
    """20 created invites/day/user (`giapha-invite-create`), approvers exempt.

    Runs after the permission classes, so the role cache is already filled.
    Only `POST` is throttled -- listing and revoking are not spam vectors.
    """

    def allow_request(self, request, view):
        if request.method != 'POST':
            return True
        member = cached_member(request, view.kwargs.get('clan_id'))
        if member is not None and member.role in APPROVER_ROLES:
            return True
        return super().allow_request(request, view)


def save_with_fresh_code(invite):
    """Mint a code and save, retrying on the rare unique collision."""
    for _ in range(MAX_CODE_ATTEMPTS):
        invite.code = generate_code()
        try:
            with transaction.atomic():
                invite.save()
            return invite
        except IntegrityError:
            continue
    raise BadRequestException('Không thể tạo mã mời, vui lòng thử lại.')


def _invite_person_or_error(clan_id, person_id):
    person = get_person_or_none(clan_id, person_id)
    if person is None:
        raise BadRequestException(PERSON_OTHER_CLAN)
    if _is_deceased(person):
        raise BadRequestException(PERSON_DECEASED)
    if person_is_claimed(person.id):
        raise BadRequestException(PERSON_CLAIMED)
    return person


class ClanInviteListCreateAPIView(APIView):
    """`GET`: approvers see every invite (`?status=` filter), others only
    their own. `POST`: any editor+, or a viewer with a verified binding.
    """

    permission_classes = [IsAuthenticated, IsClanMember]
    throttle_classes = [MemberInviteThrottle]
    throttle_scope = 'giapha-invite-create'

    def get(self, request, clan_id):
        member = cached_member(request, clan_id)
        if member.role in APPROVER_ROLES:
            invites = invites_of(clan_id)
            wanted_status = request.query_params.get('status')
            if wanted_status:
                invites = invites.filter(status=wanted_status)
        else:
            invites = invites_created_by(clan_id, request.user.id)
        return Response({'data': ClanInviteSerializer(invites, many=True).data})

    def post(self, request, clan_id):
        member = cached_member(request, clan_id)
        if member.role not in EDITOR_ROLES and not (member.person_id and member.person_verified):
            raise PermissionDenied(NOT_VERIFIED_DETAIL)

        serializer = ClanInviteCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        fields = dict(serializer.validated_data)

        person_id = fields.pop('person_id')
        if person_id is not None:
            _invite_person_or_error(clan_id, person_id)
            fields['max_uses'] = 1

        if member.role not in APPROVER_ROLES:
            if open_invite_count(clan_id, request.user.id, timezone.now()) >= MAX_OPEN_INVITES_PER_MEMBER:
                raise BadRequestException(TOO_MANY_OPEN_DETAIL.format(MAX_OPEN_INVITES_PER_MEMBER))

        scope = invite_scope_ids(member, clan_id) if person_id is not None else set()
        invite_status = invite_initial_status(member.role, fields['role'], person_id, scope)
        invite = ClanInvite(
            clan_id=clan_id, created_by=request.user, person_id=person_id, status=invite_status, **fields
        )
        if invite_status == STATUS_ACTIVE:
            save_with_fresh_code(invite)
        else:
            invite.save()
            push_to_users(
                [user_id for user_id in approver_user_ids(clan_id) if user_id != request.user.id],
                'Lời mời chờ duyệt',
                'Có lời mời vào gia phả đang chờ bạn duyệt.',
                {'type': 'invite_pending', 'clan_id': clan_id, 'invite_id': invite.id},
            )
        return Response({'data': ClanInviteSerializer(invite).data}, status=status.HTTP_201_CREATED)


class ClanInviteDetailAPIView(APIView):
    """`DELETE` revokes an invite immediately -- the remediation path for a
    leaked code. Its creator or the owner.
    """

    permission_classes = [IsAuthenticated, IsClanMember]

    def delete(self, request, clan_id, invite_id):
        invite = get_invite_by_id(clan_id, invite_id)
        if invite is None:
            raise NotFound(INVITE_NOT_FOUND)
        if invite.created_by_id != request.user.id and cached_member(request, clan_id).role != 'owner':
            raise PermissionDenied(DELETE_FORBIDDEN_DETAIL)
        invite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

