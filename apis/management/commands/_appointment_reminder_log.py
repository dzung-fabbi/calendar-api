"""The two ORM writes behind `remind_appointment_date.dispatch`.

Leading underscore so Django's command discovery ignores this module. Not in
`services/`: both functions write through the ORM (`docs/code-standards.md`
-> Layering). `DeviceToken` is giapha's -- see the cross-app note in
`apis/selectors/appointment_remind.py`.
"""

from django.db import transaction

from apis.models import AppointmentReminderLog
from giapha.models import DeviceToken
from giapha.services.fcm import DEAD_TOKEN_RESULTS, RESULT_OK

ERROR_MAX_LENGTH = 255  # AppointmentReminderLog.error
# Reported for every token of a send that raised out of `send_multicast`.
SEND_ERROR = 'send_error'


def deactivate_dead(results):
    """Retire the tokens FCM called dead (uninstalled app, malformed token).
    `ERROR_NETWORK` and 5xx are transient, so those tokens stay active.
    """
    dead = [token for token, result in results.items() if result in DEAD_TOKEN_RESULTS]
    if dead:
        DeviceToken.objects.filter(token__in=dead).update(is_active=False)


def log_attempt(appointment_id, today, results):
    """Record the attempt; True when at least one device took it.

    `update_or_create` on the (appointment, sent_on) unique pair lets a re-run
    inside the same day overwrite a `failed` row with `sent`.

    NOT A GUARD AGAINST OVERLAPPING RUNS. Two processes that both pass
    `sent_today` before either writes will both push; `update_or_create`
    resolves the unique-key race internally (it re-reads on IntegrityError),
    so the second one just overwrites the row. The daily cron is the only
    scheduled caller and never overlaps itself; if a second scheduler is ever
    added, wrap the cron line in `flock -n` (see `docs/deployment-guide.md`).
    """
    errors = [result for result in results.values() if result != RESULT_OK]
    delivered = len(errors) < len(results)
    # Savepoint so a database error here cannot poison a surrounding atomic
    # block (a `TestCase`, or any future transactional caller).
    with transaction.atomic():
        AppointmentReminderLog.objects.update_or_create(
            appointment_id=appointment_id, sent_on=today,
            defaults={
                'status': 'sent' if delivered else 'failed',
                'error': '' if delivered else ', '.join(errors)[:ERROR_MAX_LENGTH],
            },
        )
    return delivered
