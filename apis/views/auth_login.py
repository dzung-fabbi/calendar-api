"""`POST /api/auth/login`, `/api/auth/refresh`, `/api/auth/logout` -- the only login path.

Username/password in, a JWT access token plus a single-use refresh token out.
There is no client_id/client_secret: a native app cannot keep a secret, so the
concept bought nothing and is gone with django-oauth-toolkit.

Three facts about these views that are otherwise re-discovered the hard way:

  (a) A 401 is `return Response(..., status=401)`, NEVER `raise
      AuthenticationFailed`. These views have `authentication_classes = ()`,
      so `get_authenticate_header()` is empty and DRF's `handle_exception`
      would downgrade the raised exception to a 403.
  (b) `authentication_classes = ()` is deliberate on all three: a caller
      holding an expired Bearer header must still be able to log in, refresh
      or log out. `apis/views/auth_register.py` does the same for the same reason.
  (c) The payload is flat (`access_token`, `refresh_token`, `token_type`,
      `expires_in`), not `{"data": ...}`-wrapped -- the shape the old token
      endpoint had, and what every token client expects.

Wrong password, unknown username and a disabled account all answer the SAME
401 body: `ModelBackend.user_can_authenticate` already folds the inactive case
into "authenticate() returned None", and the message does the rest.
"""

from django.contrib.auth import authenticate
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apis.selectors.refresh_tokens import (
    consume_refresh_token,
    delete_refresh_token,
    issue_token_pair,
)
from apis.serializers.auth import (
    INVALID_CREDENTIALS,
    INVALID_REFRESH_TOKEN,
    LoginSerializer,
    RefreshTokenSerializer,
)


def _validated(serializer_class, request):
    """Run the serializer; return `(data, None)` or `(None, 400 response)`."""
    serializer = serializer_class(data=request.data)
    if not serializer.is_valid():
        return None, Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    return serializer.validated_data, None


# `sensitive_post_parameters` asserts it received a real `HttpRequest`, and
# DRF's `Request` is not one -- so it MUST decorate `dispatch`, never `post`.
@method_decorator(sensitive_post_parameters('password'), name='dispatch')
class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = ()
    # Per-IP; see the NUM_PROXIES caveat on DEFAULT_THROTTLE_RATES.
    # `throttle_scope` alone is a no-op: the project sets no
    # DEFAULT_THROTTLE_CLASSES, so the class must be named here.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth-login'

    def post(self, request):
        data, error = _validated(LoginSerializer, request)
        if error:
            return error
        user = authenticate(request=request, **data)
        if user is None:
            return Response({'detail': INVALID_CREDENTIALS}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(issue_token_pair(user))


# The refresh token is a credential too: keep it out of error reports.
@method_decorator(sensitive_post_parameters('refresh_token'), name='dispatch')
class RefreshTokenAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = ()
    # `throttle_scope` alone is a no-op: the project sets no
    # DEFAULT_THROTTLE_CLASSES, so the class must be named here.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth-refresh'

    def post(self, request):
        data, error = _validated(RefreshTokenSerializer, request)
        if error:
            return error
        # Rotation: the presented token is deleted (rowcount-checked, so a
        # replay races to a 401) before a new pair is minted. One transaction
        # so a failure between the two leaves the old row in place rather than
        # logging the caller out for nothing; the rowcount guard still holds,
        # InnoDB's DELETE reads the current row state.
        with transaction.atomic():
            user = consume_refresh_token(data['refresh_token'])
            if user is None or not user.is_active:
                return Response(
                    {'detail': INVALID_REFRESH_TOKEN}, status=status.HTTP_401_UNAUTHORIZED)
            return Response(issue_token_pair(user))


@method_decorator(sensitive_post_parameters('refresh_token'), name='dispatch')
class LogoutAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = ()
    # No throttle scope: a 256-bit token is not guessable and the call is one
    # indexed DELETE, so there is nothing for a limit to protect.

    def post(self, request):
        data, error = _validated(RefreshTokenSerializer, request)
        if error:
            return error
        # 204 whether or not the row existed -- logout must not be an oracle
        # for "is this token still valid".
        delete_refresh_token(data['refresh_token'])
        return Response(status=status.HTTP_204_NO_CONTENT)
