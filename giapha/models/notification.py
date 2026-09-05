"""`GioNotificationLog` -- one row per (person, recipient, giỗ date) reminder.

The `unique_together` IS the de-duplication mechanism: re-running the daily
command inside the same day finds the row and skips, so no separate "already
sent" state has to be kept in sync.

ONLY `status='sent'` BLOCKS A RESEND. Failed attempts are recorded too, but
`selectors.gio_follow.notified_pairs` reads `sent` rows only, so re-running
the command retries exactly the pairs that failed. There is no "next day's
run" to fall back on: the reminder target is `today + gio_remind_before_days`
and advances with `today`, so a person is due on exactly ONE calendar day per
year. A failed row that blocked retries would silently cost that person their
giỗ notice for the year.
"""

from django.contrib.auth.models import User
from django.db import models

from giapha.models.person import Person

GIO_NOTIFY_STATUS = (
    ('sent', 'Đã gửi'),
    ('failed', 'Thất bại'),
)


class GioNotificationLog(models.Model):
    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name='gio_notifications',
        verbose_name='Người được nhắc giỗ',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='gio_notifications',
        verbose_name='Người nhận thông báo',
    )
    # The solar date the giỗ falls on, not the date the push went out --
    # that is what makes the dedupe key stable across a retry.
    solar_date = models.DateField(db_index=True, verbose_name='Ngày giỗ dương lịch')
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name='Thời điểm gửi')
    # `status` is read by `notified_pairs` (only `sent` suppresses a resend).
    # `error` is a write-only audit trail: nothing queries it, it is truncated
    # to the column width by the command, and it exists for post-mortems.
    status = models.CharField(max_length=16, choices=GIO_NOTIFY_STATUS, verbose_name='Trạng thái')
    error = models.CharField(max_length=255, blank=True, verbose_name='Lỗi')

    class Meta:
        verbose_name = 'Nhật ký nhắc giỗ'
        verbose_name_plural = 'Nhật ký nhắc giỗ'
        unique_together = ('person', 'user', 'solar_date')

    def __str__(self):
        return '{} -> {} ({})'.format(self.person_id, self.user_id, self.solar_date)
