"""`POST /api/auth/change-password` -- authenticated password change.

Separate from `views/auth_password_reset.py` because the two answer different
questions. Reset proves possession of a MAILBOX and must reveal nothing about
whether an account exists; change proves possession of the CURRENT PASSWORD by
an already-authenticated caller, so it can afford to say plainly what is wrong.
The shared part -- setting the password and revoking every token -- lives in
`apis/selectors/auth_tokens.py`.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.selectors.auth_tokens import set_password_and_revoke_tokens
from apis.serializers.auth import ChangePasswordSerializer

CHANGE_OK = 'Đổi mật khẩu thành công. Vui lòng đăng nhập lại.'
WRONG_CURRENT_PASSWORD = 'Mật khẩu hiện tại không đúng.'
NO_USABLE_PASSWORD = 'Tài khoản chưa có mật khẩu. Vui lòng dùng chức năng quên mật khẩu.'


class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]
    # `ScopedRateThrottle` keys on the user id for an authenticated request, so
    # unlike the reset scopes this is a genuine per-user bucket -- immune to the
    # IP-rotation and per-process-cache weaknesses those suffer from.
    throttle_scope = 'auth-change-password'

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={'user': request.user},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        if not request.user.has_usable_password():
            # A legacy social account has no current password to present.
            # Point at the flow that CAN help instead of an unfalsifiable
            # "wrong password" -- the caller is already authenticated, so
            # there is nothing to leak here.
            return Response(
                {'current_password': [NO_USABLE_PASSWORD]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not request.user.check_password(data['current_password']):
            return Response(
                {'current_password': [WRONG_CURRENT_PASSWORD]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Revokes the caller's OWN token too -- they must log in again. That is
        # the agreed behaviour: a change made because a password leaked has to
        # evict every session, and once an attacker holds a valid token there
        # is no way to tell "mine" from "theirs".
        set_password_and_revoke_tokens(request.user, data['new_password'])
        return Response({'data': {'detail': CHANGE_OK}})
