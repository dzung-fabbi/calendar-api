"""Pure token functions for the JWT login flow. No ORM, no `request`.

Kept free of Django models so it runs under `SimpleTestCase`; reading
`settings` is the one dependency, as in `apis/services/otp.py`. The ORM side
(issuing, rotating and deleting refresh rows) is `apis/selectors/refresh_tokens.py`.

ACCESS TOKEN -- a HS256 JWT signed with `settings.JWT_SIGNING_KEY`, carrying:
  * `sub`  -- the user's primary key AS A STRING, as RFC 7519 requires and as
              PyJWT >= 2.10 enforces. The authenticator passes it back to
              `User.objects.get(pk=...)`, which coerces it.
  * `iat`, `exp` -- issue and expiry, both timezone-aware UTC.
  * `jti`  -- random id, so two tokens minted in the same second differ.
  * `pwd`  -- `password_fingerprint(user.password)`. This is the revocation
              mechanism: nothing about an access token is stored, so the only
              way to kill one early is to bind it to state that a password
              change rewrites. `set_password()` produces a fresh salt, hence a
              fresh hash, hence a fresh fingerprint -- and every token minted
              before it stops matching at once.

The algorithm is a module constant, NOT a setting: a configurable `alg` is how
`alg: none` downgrade attacks get in, and there is exactly one legitimate value.

REFRESH TOKEN -- `secrets.token_urlsafe(32)`, stored as a plain sha256 hex
digest. Plain, not HMAC: `apis/services/otp.py` keys its digest on SECRET_KEY
because a 6-digit code has a million possible values and the key is what stops
an offline guess. A 256-bit random token needs no such help -- its entropy is
the security, and a keyed digest would only make the lookup depend on one more
secret.
"""

import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

import jwt
from django.conf import settings

ALGORITHM = 'HS256'
FINGERPRINT_LENGTH = 16


def password_fingerprint(password_hash):
    """First 16 hex chars of sha256(user.password). Changes on every `set_password()`.

    Truncated because the claim only has to CHANGE, not be unguessable: a
    caller who could forge a token with the right `pwd` would also need the
    signing key, at which point the fingerprint is irrelevant.
    """
    return sha256((password_hash or '').encode('utf-8')).hexdigest()[:FINGERPRINT_LENGTH]


def encode_access_token(user_id, password_hash, now=None):
    """Mint an access token. Returns `(token, expires_in_seconds)`.

    `now` is injectable so a test can mint an already-expired token without
    sleeping or freezing the clock.
    """
    now = now or datetime.now(tz=timezone.utc)
    lifetime = settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS
    claims = {
        'sub': str(user_id),
        'iat': now,
        'exp': now + timedelta(seconds=lifetime),
        'jti': uuid4().hex,
        'pwd': password_fingerprint(password_hash),
    }
    # PyJWT 2.x returns `str`; 1.x returned bytes. Pinned at 2.6.0.
    return jwt.encode(claims, settings.JWT_SIGNING_KEY, algorithm=ALGORITHM), lifetime


def decode_access_token(token):
    """Verify signature and expiry, return the claims dict.

    Raises a `jwt.InvalidTokenError` subclass on any failure (bad signature,
    expired, malformed). Callers translate that to a single generic 401 --
    do not surface WHICH check failed.
    """
    # `algorithms=` is mandatory in PyJWT 2.x and also the guard against a
    # token that names a different algorithm in its header.
    return jwt.decode(token, settings.JWT_SIGNING_KEY, algorithms=[ALGORITHM])


def generate_refresh_token():
    """A fresh raw refresh token (~256 bits, 43 URL-safe chars)."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw):
    """The stored form of a raw refresh token: 64 hex chars, matching
    `RefreshToken.token_hash`'s max_length exactly."""
    return sha256(raw.encode('utf-8')).hexdigest()
