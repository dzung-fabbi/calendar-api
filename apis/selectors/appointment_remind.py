"""Reads behind `remind_appointment_date`.

CROSS-APP IMPORT, ON PURPOSE. `docs/code-standards.md` -> Decoupling forbids
`apis` <-> `giapha` imports, with one recorded exception: the push channel
(`DeviceToken`, `/devices`, `services/fcm.py`) is user-level infrastructure
that happens to live in `giapha`, and a device registers its token exactly
once. Duplicating the model would make clients register twice; so `apis`
reads the tokens through giapha's selector instead. Nothing else crosses.
"""

from django.db.models import DateField, ExpressionWrapper, F

from apis.models import AppointmentDate, AppointmentReminderLog
from giapha.selectors.gio_follow import active_tokens_for  # noqa: F401  (re-exported)


def due_appointments(today):
    """Every appointment whose daily reminder window covers `today`.

    The window is `date - before_days <= today <= date`, inclusive at both
    ends: the reminder repeats every morning until the day itself. Rows with
    no owner or no date can never be delivered and are excluded up front.
    """
    remind_on = ExpressionWrapper(
        F('date') - F('before_days'), output_field=DateField()
    )
    return list(
        AppointmentDate.objects
        .filter(user__isnull=False, date__gte=today)
        .annotate(remind_on=remind_on)
        .filter(remind_on__lte=today)
        .order_by('date', 'id')
    )


def sent_today(appointment_ids, today):
    """Ids among `appointment_ids` that already have a `sent` log for `today`.

    `failed` rows are deliberately not read: a re-run inside the same day is
    the retry for them.
    """
    appointment_ids = list(appointment_ids)
    if not appointment_ids:
        return set()
    return set(
        AppointmentReminderLog.objects
        .filter(appointment_id__in=appointment_ids, sent_on=today, status='sent')
        .values_list('appointment_id', flat=True)
    )
