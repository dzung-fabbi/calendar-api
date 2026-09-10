"""`appointment_reminder_logs` -- daily de-duplication for `remind_appointment_date`.

See `apis/models/appointment_reminder_log.py`: one row per (appointment, day),
`sent` blocks a resend that day, `failed` does not.

Also clamps legacy `appointment_dates.before_days` into the 0..365-day range the
serializer now enforces. The old view accepted any int, and a row outside the
range would otherwise (a) make the owner's own GET un-POSTable -- 400 on a row
they never touched -- and (b) overflow MySQL's `DATE_SUB` into NULL so the
reminder never fires. Not reversible: the original out-of-range values are
meaningless as lead times.
"""

import datetime as dt

from django.db import migrations, models
import django.db.models.deletion

MAX_BEFORE_DAYS = 365  # keep in step with apis/serializers/booking.py


def clamp_before_days(apps, schema_editor):
    AppointmentDate = apps.get_model('apis', 'AppointmentDate')
    AppointmentDate.objects.filter(
        before_days__gt=dt.timedelta(days=MAX_BEFORE_DAYS),
    ).update(before_days=dt.timedelta(days=MAX_BEFORE_DAYS))
    AppointmentDate.objects.filter(
        before_days__lt=dt.timedelta(0),
    ).update(before_days=dt.timedelta(0))


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0075_drop_oauth2_provider_tables'),
    ]

    operations = [
        migrations.RunPython(clamp_before_days, migrations.RunPython.noop),
        migrations.CreateModel(
            name='AppointmentReminderLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sent_on', models.DateField(verbose_name='Ngày nhắc')),
                ('status', models.CharField(choices=[('sent', 'Đã gửi'), ('failed', 'Thất bại')], max_length=8, verbose_name='Trạng thái')),
                ('error', models.CharField(blank=True, default='', max_length=255, verbose_name='Lỗi')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')),
                ('appointment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reminder_logs', to='apis.appointmentdate', verbose_name='Lịch hẹn')),
            ],
            options={
                'verbose_name': 'Nhật ký nhắc lịch hẹn',
                'verbose_name_plural': 'Nhật ký nhắc lịch hẹn',
                'db_table': 'appointment_reminder_logs',
                'unique_together': {('appointment', 'sent_on')},
            },
        ),
    ]
