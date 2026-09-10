"""Issue, rotate and delete refresh tokens -- the only ORM in the token path.

The pure half (encoding, hashing) is `apis/services/jwt_tokens.py`; this module
owns the `RefreshToken` rows. Bulk eviction on password change lives in
`apis/selectors/auth_tokens.py`.
"""

from datetime import timedelta
from hmac import compare_digest

from django.conf import settings
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from apis.models import RefreshToken
from apis.services.jwt_tokens import (
    encode_access_token,
    generate_refresh_token,
    hash_refresh_token,
    password_fingerprint,
)


@sensitive_variables('raw')
def issue_token_pair(user):
    """Mint an access token and a NEW refresh row. Returns the response payload.

    The raw refresh token is returned here, once, and never stored -- only its
    hash is. Same payload shape for login and refresh so a client has one
    parser.
    """
    raw = generate_refresh_token()
    RefreshToken.objects.create(
        user=user,
        token_hash=hash_refresh_token(raw),
        password_fingerprint=password_fingerprint(user.password),
        expires_at=timezone.now() + timedelta(
            seconds=settings.JWT_REFRESH_TOKEN_LIFETIME_SECONDS,
        ),
    )
    access_token, expires_in = encode_access_token(user.pk, user.password)
    return {
        'access_token': access_token,
        'refresh_token': raw,
        'token_type': 'Bearer',
        'expires_in': expires_in,
    }


@sensitive_variables('raw')
def consume_refresh_token(raw):
    """Delete the live row `raw` names and return its user, or None.

    The DELETE's rowcount is the race check. Two concurrent refreshes with
    the same token both read the row; only one DELETE removes it, the loser
    sees 0 rows and gets None -> 401. Without this a replayed token could
    hand out two live sessions before either caller noticed.

    The row is DELETED even when it then fails the password check: a token
    issued before a password change is dead either way, and leaving it would
    let the same stale token be retried forever.

    Expired rows are filtered out here rather than deleted: they are inert
    (this is the only path that reads them) and the prune is an operator
    concern -- see docs/deployment-guide.md.
    """
    row = (
        RefreshToken.objects
        .filter(token_hash=hash_refresh_token(raw), expires_at__gt=timezone.now())
        .select_related('user')
        .first()
    )
    if row is None:
        return None
    deleted, _ = RefreshToken.objects.filter(pk=row.pk).delete()
    if not deleted:
        return None
    # Password rewritten since issue (admin, shell, changepassword, ...): the
    # row survived because nothing deleted it, but it must not mint again.
    if not compare_digest(row.password_fingerprint, password_fingerprint(row.user.password)):
        return None
    return row.user


@sensitive_variables('raw')
def delete_refresh_token(raw):
    """Logout. Returns the number of rows removed; 0 is not an error.

    Answering the same way for a known and an unknown token keeps logout from
    becoming a token-validity oracle.
    """
    return RefreshToken.objects.filter(token_hash=hash_refresh_token(raw)).delete()[0]
