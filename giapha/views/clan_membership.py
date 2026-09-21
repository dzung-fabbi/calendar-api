"""Clan member roster and role/removal management.

Invites live in `views/clan_invite.py` + `views/invite_review.py`, joining in
`views/clan_join.py`, binding verification in `views/member_verify.py`.
"""

from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.models import ClanInvite
from giapha.permissions import IsClanMember, IsClanOwner
from giapha.selectors.clan import member_by_user_id, members_of, owner_count
from giapha.selectors.family_link_detach import detach_for_member
from giapha.selectors.person import get_person_or_none
from giapha.serializers.clan import ClanMemberRoleUpdateSerializer, ClanMemberSerializer

MEMBER_NOT_FOUND = 'Không tìm thấy thành viên.'
LAST_OWNER_DETAIL = 'Dòng họ phải có ít nhất một chủ sở hữu.'
SCOPE_EDITOR_ONLY_DETAIL = 'Chỉ biên tập viên mới được giới hạn theo chi; trưởng họ và Ban quản lý luôn quản toàn họ.'
SCOPE_ROOT_NOT_FOUND = 'Không tìm thấy người làm gốc chi trong dòng họ này.'


class ClanMembersAPIView(APIView):
    """`GET` the member roster. Any role may view it."""

    permission_classes = [IsAuthenticated, IsClanMember]

    def get(self, request, clan_id):
        members = members_of(clan_id)
        context = {'request': request}
        return Response({'data': ClanMemberSerializer(members, many=True, context=context).data})


class ClanMemberDetailAPIView(APIView):
    """`PATCH` changes a member's role, `DELETE` removes them. Owner only --
    including assigning/removing `manager` (Ban quản lý).
    """

    permission_classes = [IsAuthenticated, IsClanOwner]

    def patch(self, request, clan_id, user_id):
        member = member_by_user_id(clan_id, user_id)
        if member is None:
            raise NotFound(MEMBER_NOT_FOUND)

        serializer = ClanMemberRoleUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        new_role = data.get('role', member.role)
        if member.role == 'owner' and new_role != 'owner' and owner_count(clan_id) <= 1:
            raise BadRequestException(LAST_OWNER_DETAIL)

        scope_root = data.get('scope_root_person_id', member.scope_root_person_id)
        if new_role != 'editor':
            if data.get('scope_root_person_id'):
                raise BadRequestException(SCOPE_EDITOR_ONLY_DETAIL)
            scope_root = None  # leaving `editor` clears the branch
        elif scope_root is not None and get_person_or_none(clan_id, scope_root) is None:
            raise BadRequestException(SCOPE_ROOT_NOT_FOUND)

        member.role = new_role
        member.scope_root_person_id = scope_root
        member.save(update_fields=['role', 'scope_root_person'])
        return Response({'data': ClanMemberSerializer(member, context={'request': request}).data})

    def delete(self, request, clan_id, user_id):
        member = member_by_user_id(clan_id, user_id)
        if member is None:
            raise NotFound(MEMBER_NOT_FOUND)

        if member.role == 'owner' and owner_count(clan_id) <= 1:
            raise BadRequestException(LAST_OWNER_DETAIL)

        with transaction.atomic():
            # Their personal-tree links into this clan detach (snapshot first).
            detach_for_member(clan_id, member.user_id)
            # Codes they minted must not let them (or an alt) back in (review H3).
            ClanInvite.objects.filter(clan_id=clan_id, created_by_id=member.user_id).delete()
            member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
