"""One-time codes for the password-reset flow (`apis/views/auth_password_reset.py`).

WHY A MODEL AND NOT `django.contrib.auth.tokens.default_token_generator`:
that generator is stateless -- it derives a long URL-safe token from the
password hash and verifies it by recomputation. Nothing about it can express
the three controls that actually make a *6-digit* code safe: a per-code
attempt counter, single use, and a short absolute lifetime. A 6-digit code
has only a million possible values, so those controls are the security, not
the code's own entropy.

THE CODE IS NEVER STORED. Only `code_hash` is -- see `apis/services/otp.py`
for why that is an HMAC keyed on SECRET_KEY rather than a password hash.
"""

from django.contrib.auth.models import User
from django.db import models


class PasswordResetCode(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_reset_codes',
        verbose_name='Người dùng',
    )
    code_hash = models.CharField(max_length=64, verbose_name='Mã băm')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(verbose_name='Hết hạn lúc')
    attempts = models.PositiveSmallIntegerField(default=0, verbose_name='Số lần thử')
    # Set both when the code is spent on a successful reset AND when it is
    # superseded by a newer request, so "still usable" is one condition
    # (`used_at IS NULL`) rather than two.
    used_at = models.DateTimeField(null=True, blank=True, verbose_name='Đã dùng lúc')

    class Meta:
        verbose_name = 'Mã đặt lại mật khẩu'
        verbose_name_plural = 'Mã đặt lại mật khẩu'
        indexes = [
            models.Index(fields=['user', 'used_at'], name='prc_user_used_idx'),
        ]

    def __str__(self):
        return 'Mã đặt lại mật khẩu #{} (user={})'.format(self.pk, self.user_id)
