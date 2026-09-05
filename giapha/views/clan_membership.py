"""Clan member roster, role/removal management, invite issuing/listing/
revocation and joining.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.models import INVITE_ROLE, ClanInvite, ClanMember
from giapha.permissions import IsClanMember, IsClanOwner
from giapha.selectors.clan import (
    get_invite_by_id,
    get_invite_for_update,
    invites_of,
    member_by_user_id,
    members_of,
    owner_count,
)
from giapha.serializers.clan import (
    ClanInviteCreateSerializer,
    ClanInviteSerializer,
    ClanMemberRoleUpdateSerializer,
    ClanMemberSerializer,
    JoinClanSerializer,
)
from giapha.services.invite_code import generate_code, is_exhausted, is_expired

MEMBER_NOT_FOUND = 'Không tìm thấy thành viên.'
LAST_OWNER_DETAIL = 'Dòng họ phải có ít nhất một chủ sở hữu.'
INVITE_NOT_FOUND = 'Không tìm thấy mã mời.'
INVALID_CODE_DETAIL = 'Mã mời không hợp lệ.'
CODE_REJECTED_DETAIL = 'Mã mời đã hết hạn hoặc hết lượt sử dụng.'
INVALID_INVITE_ROLE_DETAIL = 'Mã mời có vai trò không hợp lệ, vui lòng xin mã mới.'

_INVITE_ROLE_VALUES = frozenset(value for value, _label in INVITE_ROLE)
MAX_CODE_ATTEMPTS = 5


class ClanMembersAPIView(APIView):
    """`GET` the member roster. Any role may view it."""

    permission_classes = [IsAuthenticated, IsClanMember]

    def get(self, request, clan_id):
        members = members_of(clan_id)
        context = {'request': request}
        return Response({'data': ClanMemberSerializer(members, many=True, context=context).data})


class ClanMemberDetailAPIView(APIView):
    """`PATCH` changes a member's role, `DELETE` removes them. Owner only."""

    permission_classes = [IsAuthenticated, IsClanOwner]

    def patch(self, request, clan_id, user_id):
        member = member_by_user_id(clan_id, user_id)
        if member is None:
            raise NotFound(MEMBER_NOT_FOUND)

        serializer = ClanMemberRoleUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        new_role = serializer.validated_data['role']
        if member.role == 'owner' and new_role != 'owner' and owner_count(clan_id) <= 1:
            raise BadRequestException(LAST_OWNER_DETAIL)

        member.role = new_role
        member.save(update_fields=['role'])
        return Response({'data': ClanMemberSerializer(member, context={'request': request}).data})

    def delete(self, request, clan_id, user_id):
        member = member_by_user_id(clan_id, user_id)
        if member is None:
            raise NotFound(MEMBER_NOT_FOUND)

        if member.role == 'owner' and owner_count(clan_id) <= 1:
            raise BadRequestException(LAST_OWNER_DETAIL)

        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClanInviteListCreateAPIView(APIView):
    """`GET` lists every invite ever issued for the clan -- the remediation
    path for a leaked code (see `ClanInviteDetailAPIView.delete`). `POST`
    generates a new one. Owner only, both ways.
    """

    permission_classes = [IsAuthenticated, IsClanOwner]

    def get(self, request, clan_id):
        invites = invites_of(clan_id)
        return Response({'data': ClanInviteSerializer(invites, many=True).data})

    def post(self, request, clan_id):
        serializer = ClanInviteCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        invite = self._create_invite(clan_id, request.user, serializer.validated_data)
        return Response({'data': ClanInviteSerializer(invite).data}, status=status.HTTP_201_CREATED)

    @staticmethod
    def _create_invite(clan_id, created_by, fields):
        """Generate a code and insert it, retrying on the rare unique collision."""
        for _ in range(MAX_CODE_ATTEMPTS):
            try:
                with transaction.atomic():
                    return ClanInvite.objects.create(
                        clan_id=clan_id, code=generate_code(), created_by=created_by, **fields,
                    )
            except IntegrityError:
                continue
        raise BadRequestException('Không thể tạo mã mời, vui lòng thử lại.')


class ClanInviteDetailAPIView(APIView):
    """`DELETE` revokes an invite immediately -- the only remediation path
    for a leaked code. Owner only.
    """

    permission_classes = [IsAuthenticated, IsClanOwner]

    def delete(self, request, clan_id, invite_id):
        invite = get_invite_by_id(clan_id, invite_id)
        if invite is None:
            raise NotFound(INVITE_NOT_FOUND)
        invite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class JoinClanAPIView(APIView):
    """`POST {code}` redeems an invite code for the calling user.

    Scoped-throttled (only this endpoint, not project-wide -- `apis/`
    deliberately has none) to blunt brute-forcing the 40-bit code space.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'giapha-join'

    def post(self, request):
        serializer = JoinClanSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        code = serializer.validated_data['code']

        with transaction.atomic():
            invite = get_invite_for_update(code)
            if invite is None:
                raise NotFound(INVALID_CODE_DETAIL)

            # Idempotent: already a member -> no second row, still 200.
            member = member_by_user_id(invite.clan_id, request.user.id)
            if member is None:
                if is_expired(invite, timezone.now()) or is_exhausted(invite):
                    raise BadRequestException(CODE_REJECTED_DETAIL)
                # Re-check the role at redemption, not just at creation: the
                # serializer caps new invites at INVITE_ROLE, but a row written
                # through Django admin (or predating that cap) bypasses it
                # entirely, and this is the line that actually grants the role.
                # Fail closed -- never silently hand out something weaker or
                # stronger than asked for.
                if invite.role not in _INVITE_ROLE_VALUES:
                    raise BadRequestException(INVALID_INVITE_ROLE_DETAIL)
                member = ClanMember.objects.create(
                    clan_id=invite.clan_id, user=request.user, role=invite.role,
                )
                invite.used_count += 1
                invite.save(update_fields=['used_count'])

        return Response({'data': ClanMemberSerializer(member, context={'request': request}).data}, status=status.HTTP_200_OK)
