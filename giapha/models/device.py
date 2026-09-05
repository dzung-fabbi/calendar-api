"""`DeviceToken` -- an FCM registration token belonging to a user.

A token identifies a device installation, not a clan: a user in three clans
has one token, and the reminder job fans out to whatever tokens the resolved
recipients own. That is why `/devices` is `IsAuthenticated` only.

Tokens are credentials. `__str__` deliberately never renders one so an admin
list, a log line or a traceback cannot leak it, and no serializer outside
`serializers/device.py` reads the field.
"""

from django.contrib.auth.models import User
from django.db import models

DEVICE_PLATFORM = (
    ('ios', 'iOS'),
    ('android', 'Android'),
    ('web', 'Web'),
)


class DeviceToken(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='device_tokens', verbose_name='Người dùng',
    )
    # Unique so `POST /devices` is a genuine upsert keyed by the token: a
    # shared handset re-registering under a second account transfers the row
    # instead of creating a duplicate that would push to the wrong person.
    token = models.CharField(max_length=255, unique=True, verbose_name='Token thiết bị')
    platform = models.CharField(max_length=16, choices=DEVICE_PLATFORM, verbose_name='Nền tảng')
    # Set to False when FCM reports the token UNREGISTERED/INVALID_ARGUMENT,
    # so a dead device stops being retried without losing the audit row.
    is_active = models.BooleanField(default=True, verbose_name='Còn hiệu lực')
    last_seen = models.DateTimeField(auto_now=True, verbose_name='Lần cuối hoạt động')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')

    class Meta:
        verbose_name = 'Thiết bị nhận thông báo'
        verbose_name_plural = 'Thiết bị nhận thông báo'

    def __str__(self):
        # Never the token itself -- see module docstring.
        return 'user={} platform={}'.format(self.user_id, self.platform)
