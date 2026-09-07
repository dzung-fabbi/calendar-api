"""Password recovery by emailed OTP.

`POST /api/auth/forgot-password`  -> mail a 6-digit code
`POST /api/auth/verify-otp`       -> check a code without spending it
`POST /api/auth/reset-password`   -> spend a code, set a new password

TWO RULES GOVERN EVERYTHING IN THIS MODULE.

1. NO ACCOUNT ENUMERATION. `forgot-password` answers the same 200 body for a
   registered address, an unknown one, an inactive account, a user who has hit
   the per-user cap, and a failed send. A different status, body -- or a 503
   when SMTP breaks -- would turn the endpoint into an "is this person a
   user?" oracle for anyone holding a list of email addresses. The 503 case is
   the subtle one: a send is only ATTEMPTED for accounts that exist, so
   surfacing its failure leaks exactly the fact being protected.

   ACCEPTED RISK: the timing still differs. The existing-user branch hashes,
   writes and talks to an SMTP server; the unknown branch returns immediately.
   Closing that needs either a task queue (no broker in this project) or a
   sleep on every request (which ties up a worker per probe -- a worse problem
   than the leak). `EMAIL_TIMEOUT` bounds the worst case. Registration is a
   cheaper oracle anyway (see `views/auth_register.py`), so closing this one
   alone would buy nothing.

2. THE ATTEMPT COUNTER IS THE REAL DEFENCE. A 6-digit code has 10**6 values,
   which a distributed attacker can walk quickly; the per-IP throttles cannot
   stop that (`NUM_PROXIES` is 0, so buckets key on REMOTE_ADDR, and there is
   no shared cache, so each worker process holds its own bucket). What holds
   is per-code and per-user state: one live code at a time, dead after
   `PASSWORD_RESET_MAX_ATTEMPTS` wrong guesses, gone after the TTL, plus a
   per-USER request cap that no amount of IP rotation escapes.

   Lockout is per CODE, never per account: an account-level lock would let
   anyone who knows a victim's address lock them out at will.

LEGACY ACCOUNTS RESET TOO. Users left over from the removed Facebook/Google
login have `set_unusable_password()`. Reset is deliberately NOT gated on
`has_usable_password()` -- possession of the mailbox is the proof, and before
this flow existed those accounts had no recovery path at all
(`docs/deployment-guide.md`). Refusing them would leak account type as well.
"""

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.selectors.auth_tokens import set_password_and_revoke_tokens
from apis.selectors.password_reset import (
    MAX_REQUESTS_PER_HOUR,
    active_code_for,
    issue_code,
    recent_request_count,
    user_for_email,
)
from apis.serializers.auth import (
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    VerifyOtpSerializer,
)
from apis.services.mailer import send_password_reset_code
from apis.services.otp import codes_match, generate_code

# Deliberately says "if the address is registered" -- the response is identical
# for an unknown address, so this wording keeps it from being a lie either way.
FORGOT_SENT = 'Nếu email đã đăng ký, mã đặt lại mật khẩu đã được gửi tới hộp thư của bạn.'
RESET_OK = 'Đặt lại mật khẩu thành công. Vui lòng đăng nhập lại.'
INVALID_CODE = 'Mã không đúng hoặc đã hết hạn.'
TOO_MANY_ATTEMPTS = 'Bạn đã nhập sai quá nhiều lần. Vui lòng yêu cầu mã mới.'


def check_code(user, code):
    """`(code_row, error_message)`. Exactly one of the two is None.

    Records the failed attempt on the row itself, so guesses are counted per
    code and survive the attacker changing IP.
    """
    code_row = active_code_for(user) if user is not None else None
    if code_row is None:
        return None, INVALID_CODE
    if code_row.attempts >= settings.PASSWORD_RESET_MAX_ATTEMPTS:
        return None, TOO_MANY_ATTEMPTS
    if not codes_match(code_row.code_hash, code, user.pk):
        code_row.attempts += 1
        code_row.save(update_fields=['attempts'])
        # Report exhaustion on the attempt that causes it, so the client can
        # say "request a new code" instead of letting the user keep typing.
        if code_row.attempts >= settings.PASSWORD_RESET_MAX_ATTEMPTS:
            return None, TOO_MANY_ATTEMPTS
        return None, INVALID_CODE
    return code_row, None


class ForgotPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    # The default OAuth2 authenticator would reject a stale bearer header with
    # a 401 before this view ran; someone who cannot log in must still be able
    # to ask for a code.
    authentication_classes = ()
    throttle_scope = 'auth-forgot-password'

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        user = user_for_email(email)
        if user is not None and recent_request_count(user) < MAX_REQUESTS_PER_HOUR:
            code = generate_code()
            issue_code(user, code)
            # Return value ignored on purpose: a send failure must not change
            # the response (see rule 1). The mailer logs it.
            send_password_reset_code(
                user.email or email, code, settings.PASSWORD_RESET_CODE_TTL_SECONDS,
            )

        return Response({'data': {'detail': FORGOT_SENT}})


class VerifyOtpAPIView(APIView):
    """Checks a code WITHOUT spending it, so the app can validate its code
    screen before showing the new-password screen.

    A wrong guess here still counts against the attempt cap. If it did not,
    this endpoint would be a free brute-force oracle for `reset-password`.
    """

    permission_classes = [AllowAny]
    authentication_classes = ()
    throttle_scope = 'auth-reset-password'

    def post(self, request):
        serializer = VerifyOtpSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        _, error = check_code(user_for_email(data['email']), data['code'])
        if error:
            return Response({'code': [error]}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'data': {'valid': True}})


class ResetPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = ()
    throttle_scope = 'auth-reset-password'

    def post(self, request):
        # Serializer first, so a weak `new_password` is rejected BEFORE the
        # code is checked -- a correct code must not be burnt by a password the
        # user is then asked to retype.
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user = user_for_email(data['email'])
        code_row, error = check_code(user, data['code'])
        if error:
            return Response({'code': [error]}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            set_password_and_revoke_tokens(user, data['new_password'])
            code_row.used_at = timezone.now()
            code_row.save(update_fields=['used_at'])
        return Response({'data': {'detail': RESET_OK}})
