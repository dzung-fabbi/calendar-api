"""`AppointmentReminderLog` -- one row per (appointment, calendar day) push attempt.

The reminder is DAILY: from `date - before_days` up to and including `date`
the owner gets one push a day. The `unique_together` on (appointment,
sent_on) is the de-duplication: re-running `remind_appointment_date` inside
the same day finds the row and skips, so no extra "already sent" flag has to
be kept on `AppointmentDate`.

ONLY `status='sent'` BLOCKS A RESEND. A `failed` row is kept for the audit
trail, but `selectors.appointment_remind.sent_today` reads `sent` rows only,
so a re-run after an outage retries exactly the appointments that failed.
Same contract as `giapha.GioNotificationLog`.
"""

from django.db import models

from apis.models.booking import AppointmentDate

REMINDER_STATUS = (
    ('sent', 'Đã gửi'),
    ('failed', 'Thất bại'),
)


class AppointmentReminderLog(models.Model):
    appointment = models.ForeignKey(
        AppointmentDate, on_delete=models.CASCADE, related_name='reminder_logs',
        verbose_name='Lịch hẹn',
    )
    # The Vietnam calendar day the reminder was for, not the send timestamp:
    # the command runs once a day and this is what the uniqueness is keyed on.
    sent_on = models.DateField(verbose_name='Ngày nhắc')
    status = models.CharField(max_length=8, choices=REMINDER_STATUS, verbose_name='Trạng thái')
    error = models.CharField(max_length=255, blank=True, default='', verbose_name='Lỗi')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')

    class Meta:
        db_table = 'appointment_reminder_logs'
        unique_together = ('appointment', 'sent_on')
        verbose_name = 'Nhật ký nhắc lịch hẹn'
        verbose_name_plural = 'Nhật ký nhắc lịch hẹn'

    def __str__(self):
        return 'appointment={} {} {}'.format(self.appointment_id, self.sent_on, self.status)
