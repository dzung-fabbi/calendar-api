"""`POST /join {code}` -- redeem an invite code for the calling user.

Scoped-throttled (only this endpoint, not project-wide -- `apis/`
deliberately has none) to blunt brute-forcing the 40-bit code space.

An invite that names a person binds the new member to that node, verified,
in the same transaction. If someone claimed the node in between, the join
still succeeds -- only without the binding (`binding: null` + `message`),
because refusing entry over a race the invitee cannot see would be worse.
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
from giapha.models import INVITE_ROLE, ClanMember
from giapha.selectors.clan import get_invite_for_update, member_by_user_id
from giapha.selectors.invite import lock_person_for_claim, person_is_claimed
from giapha.serializers.clan import ClanMemberSerializer
from giapha.serializers.clan_invite import JoinClanSerializer
from giapha.services.invite_code import is_exhausted, is_expired
from giapha.services.invite_policy import STATUS_ACTIVE
from giapha.views.member_binding import binding_payload

INVALID_CODE_DETAIL = 'Mã mời không hợp lệ.'
CODE_REJECTED_DETAIL = 'Mã mời đã hết hạn hoặc hết lượt sử dụng.'
INVALID_INVITE_ROLE_DETAIL = 'Mã mời có vai trò không hợp lệ, vui lòng xin mã mới.'
BINDING_LOST_DETAIL = 'Đã vào dòng họ, nhưng người được mời đã có thành viên khác nhận. Hãy chọn lại mình là ai trong cây.'

_INVITE_ROLE_VALUES = frozenset(value for value, _label in INVITE_ROLE)


def _bind_invited_person(member, invite):
    """Bind `member` to `invite.person` (verified). False if the node is
    gone or already claimed -- the caller reports that, it is not an error.
    """
    person = lock_person_for_claim(invite.clan_id, invite.person_id)
    if person is None or person_is_claimed(person.id):
        return False
    member.person = person
    member.person_verified = True
    try:
        with transaction.atomic():
            member.save(update_fields=['person', 'person_verified'])
    except IntegrityError:
        member.person = None
        member.person_verified = False
        return False
    return True


class JoinClanAPIView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'giapha-join'

    def post(self, request):
        serializer = JoinClanSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        code = serializer.validated_data['code']

        message = None
        with transaction.atomic():
            invite = get_invite_for_update(code)
            # A non-active invite normally has no code at all; the status
            # check covers rows edited through admin.
            if invite is None or invite.status != STATUS_ACTIVE:
                raise NotFound(INVALID_CODE_DETAIL)

            # Idempotent: already a member -> no second row, still 200.
            member = member_by_user_id(invite.clan_id, request.user.id)
            if member is None:
                if is_expired(invite, timezone.now()) or is_exhausted(invite):
                    raise BadRequestException(CODE_REJECTED_DETAIL)
                # Re-check the role at redemption, not just at creation: a row
                # written through Django admin bypasses the serializer cap, and
                # this is the line that actually grants the role. Fail closed.
                if invite.role not in _INVITE_ROLE_VALUES:
                    raise BadRequestException(INVALID_INVITE_ROLE_DETAIL)
                member = ClanMember.objects.create(
                    clan_id=invite.clan_id, user=request.user, role=invite.role,
                )
                invite.used_count += 1
                invite.save(update_fields=['used_count'])
                if invite.person_id and not _bind_invited_person(member, invite):
                    message = BINDING_LOST_DETAIL

        body = {
            # The member payload has no clan id; without it a client that is
            # already a member cannot tell which clan the code opened.
            'clan_id': invite.clan_id,
            'data': ClanMemberSerializer(member, context={'request': request}).data,
            'binding': binding_payload(member),
        }
        if message:
            body['message'] = message
        return Response(body, status=status.HTTP_200_OK)
