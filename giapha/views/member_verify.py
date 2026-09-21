"""`POST`/`DELETE /clans/{clan_id}/members/{user_id}/verify` -- confirm or
reject a member's self-claimed binding ("tôi là X").

Who: owner + manager, and a branch editor (trưởng chi) for nodes inside
their branch (`permissions_scope.can_verify_binding`, phase 6). Plain
editors do not verify: a verified binding is a write grant over a whole
family scope, so it is an approver decision. `POST` sets
`person_verified=True`; `DELETE` removes the binding (the member stays in
the clan, just unbound).
"""

from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.notifications import push_to_users
from giapha.permissions import IsClanEditor
from giapha.permissions_scope import can_verify_binding
from giapha.selectors.gio_follow import member_binding
from giapha.serializers.clan import ClanMemberSerializer

MEMBER_NOT_FOUND = 'Không tìm thấy thành viên.'
NO_BINDING_DETAIL = 'Thành viên này chưa nhận mình là ai trong cây.'
CANNOT_VERIFY_DETAIL = 'Chỉ trưởng họ, Ban quản lý hoặc trưởng chi có chi chứa người này mới xác minh được.'


def _bound_member_or_error(request, clan_id, user_id):
    member = member_binding(clan_id, user_id)
    if member is None:
        raise NotFound(MEMBER_NOT_FOUND)
    if member.person_id is None:
        raise BadRequestException(NO_BINDING_DETAIL)
    if not can_verify_binding(request, clan_id, member.person_id):
        raise PermissionDenied(CANNOT_VERIFY_DETAIL)
    return member


class ClanMemberVerifyAPIView(APIView):
    permission_classes = [IsAuthenticated, IsClanEditor]

    def post(self, request, clan_id, user_id):
        member = _bound_member_or_error(request, clan_id, user_id)
        if not member.person_verified:
            member.person_verified = True
            member.save(update_fields=['person_verified'])
            push_to_users(
                [member.user_id], 'Đã xác minh',
                'Bạn đã được xác minh là "{}" trong gia phả.'.format(member.person.ho_ten),
                {'type': 'binding_verified', 'clan_id': clan_id, 'person_id': member.person_id},
            )
        return Response({'data': ClanMemberSerializer(member, context={'request': request}).data})

    def delete(self, request, clan_id, user_id):
        member = _bound_member_or_error(request, clan_id, user_id)
        ho_ten = member.person.ho_ten
        member.person = None
        member.person_verified = False
        member.save(update_fields=['person', 'person_verified'])
        push_to_users(
            [member.user_id], 'Chưa xác minh được',
            'Yêu cầu nhận là "{}" trong gia phả không được chấp nhận.'.format(ho_ten),
            {'type': 'binding_rejected', 'clan_id': clan_id},
        )
        return Response({'data': ClanMemberSerializer(member, context={'request': request}).data})
