"""Refresh tokens for the JWT login flow (`apis/views/auth_login.py`).

ACCESS tokens are stateless JWTs (`apis/services/jwt_tokens.py`) and have no
row here. Only the long-lived REFRESH token is stored, and only as a sha256
hash: the raw value is handed to the client exactly once at issue time and
cannot be recovered from this table, so a database dump yields nothing a
caller could present.

THERE IS NO `revoked_at` COLUMN, ON PURPOSE. "Revoked" means "the row is
gone". Rotation on refresh, logout and password change all DELETE. The
predecessor (django-oauth-toolkit) soft-revoked with a timestamp and its own
refresh grant still honoured the row inside the grace window -- see
`docs/system-architecture.md`. A shape with no revoked-but-present state
cannot have that bug.
"""

from django.contrib.auth.models import User
from django.db import models


class RefreshToken(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='refresh_tokens',
        verbose_name='Người dùng',
    )
    # sha256 hex digest of the raw token -- 64 chars exactly. Unique so the
    # lookup on refresh/logout is an index seek and a raw token can only ever
    # name one row.
    token_hash = models.CharField(max_length=64, unique=True, verbose_name='Token băm')
    # `password_fingerprint(user.password)` at issue time. Checked on refresh,
    # so a password rewritten ANYWHERE -- admin, `manage.py changepassword`, a
    # shell `set_password()` -- kills the row's ability to mint, not only the
    # two API endpoints that also delete rows explicitly.
    password_fingerprint = models.CharField(max_length=16, verbose_name='Dấu vết mật khẩu')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True, verbose_name='Hết hạn lúc')

    class Meta:
        verbose_name = 'Refresh token'
        verbose_name_plural = 'Refresh token'

    def __str__(self):
        # Never the hash: it is the credential's only stored form.
        return 'Refresh token #{} (user={})'.format(self.pk, self.user_id)
