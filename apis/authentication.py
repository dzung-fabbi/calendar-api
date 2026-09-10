"""DRF authentication for `Authorization: Bearer <jwt>`.

Wired in as a SETTINGS STRING (`REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']`
in `djangopj/settings.py`), so `giapha/` keeps importing nothing from `apis/`
-- DRF resolves the path, the decoupling rule in `docs/code-standards.md` holds.

Two behaviours here are load-bearing and easy to lose:

  * `authenticate()` RETURNS NONE when the header is absent or is not
    `Bearer`. Raising instead would turn every anonymous request to a public
    endpoint (`/api/home`, `/api/calendar`, ...) into a 401.
  * `authenticate_header()` is implemented. Without it DRF's
    `APIView.handle_exception` downgrades `NotAuthenticated` to a 403, and
    every test asserting 401 for an anonymous caller fails.

Every failure mode -- bad signature, expired, unknown user, inactive user,
password changed since issue -- shares ONE message. A caller must not be able
to learn which check rejected them.
"""

from hmac import compare_digest

import jwt
from django.contrib.auth.models import User
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from apis.services.jwt_tokens import decode_access_token, password_fingerprint

INVALID_TOKEN = 'Token không hợp lệ hoặc đã hết hạn.'
INVALID_HEADER = 'Header Authorization không hợp lệ.'


class JWTAuthentication(BaseAuthentication):
    keyword = 'Bearer'

    def authenticate(self, request):
        header = get_authorization_header(request).split()
        if not header or header[0].lower() != self.keyword.lower().encode():
            return None  # anonymous, NOT an error -- public endpoints must still work
        if len(header) != 2:
            raise AuthenticationFailed(INVALID_HEADER)

        try:
            claims = decode_access_token(header[1].decode('utf-8'))
        except (jwt.InvalidTokenError, UnicodeDecodeError):
            raise AuthenticationFailed(INVALID_TOKEN)

        try:
            user = User.objects.get(pk=claims.get('sub'))
        except (User.DoesNotExist, ValueError, TypeError):
            raise AuthenticationFailed(INVALID_TOKEN)
        if not user.is_active:
            raise AuthenticationFailed(INVALID_TOKEN)
        # The `pwd` claim is the only revocation there is for an access token:
        # it stops matching the moment the password row changes.
        if not compare_digest(str(claims.get('pwd', '')), password_fingerprint(user.password)):
            raise AuthenticationFailed(INVALID_TOKEN)
        return (user, claims)

    def authenticate_header(self, request):
        # Load-bearing: without it DRF answers 403, not 401, for anonymous callers.
        return '{} realm="api"'.format(self.keyword)
