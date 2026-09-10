"""`python manage.py remind_appointment_date` -- nhắc lịch hẹn hằng ngày qua FCM.

Run once a day by cron (see `docs/deployment-guide.md`), same slot as
`remind_death_anniversary`. No Celery: one job a day does not justify a broker.

DAILY, NOT ONCE: an appointment with `before_days=3` produces a push on each
of the four mornings `date-3 .. date`. `AppointmentReminderLog` (one row per
appointment per day) is what makes a same-day re-run send nothing twice, and
what lets that re-run retry the rows that failed.

TWO HALVES: `collect_due(today)` does every read and returns `(jobs, skipped,
due)` with device tokens already resolved; `dispatch(jobs, today)` is the only half
that touches the network (its ORM writes live in `_appointment_reminder_log.py`).
The wording and the timezone helper are in `services/appointment_remind.py`.

TIMEZONE: `today_vn()`, never `timezone.localdate()`. `settings.TIME_ZONE` is
UTC, so a cron firing at 05:00 Vietnam time would compute *yesterday*.

QUERY BUDGET: three reads for the whole run (due rows, device tokens, today's
log) plus one write per push actually attempted.

FCM lives in `giapha` -- the one sanctioned cross-app import, recorded in
`docs/code-standards.md` -> Decoupling and `apis/selectors/appointment_remind.py`.
"""

import logging
from collections import namedtuple

from django.core.management.base import BaseCommand

from apis.management.commands._appointment_reminder_log import (
    SEND_ERROR,
    deactivate_dead,
    log_attempt,
)
from apis.selectors.appointment_remind import (
    active_tokens_for,
    due_appointments,
    sent_today,
)
from apis.services.appointment_remind import TITLE, message_body, push_data, today_vn
from giapha.services.fcm import send_multicast

logger = logging.getLogger(__name__)

# One appointment plus the owner's active device tokens.
ReminderJob = namedtuple('ReminderJob', 'appointment_id name date tokens')


def collect_due(today):
    """`(jobs, skipped, due)`: what to push today, how many were already
    pushed today, and how many appointments are in their window at all.

    An owner with no active device is dropped rather than logged as a
    failure: nothing was attempted, so nothing is owed a row. Such rows count
    in `due` but appear in neither `jobs` nor `skipped`.
    """
    rows = due_appointments(today)
    tokens = active_tokens_for(set(row.user_id for row in rows))
    already = sent_today([row.id for row in rows], today)

    jobs = []
    skipped = 0
    for row in rows:
        if row.id in already:
            skipped += 1
            continue
        if not tokens.get(row.user_id):
            continue
        jobs.append(ReminderJob(
            appointment_id=row.id, name=row.name, date=row.date,
            tokens=tokens[row.user_id],
        ))
    return jobs, skipped, len(rows)


def dispatch(jobs, today):
    """Send `jobs`. Returns `(sent, configured)`.

    `configured` is False ONLY when `send_multicast` answered `{}` to a
    non-empty token list, which it reserves for "no usable service account".
    Transient failures arrive per token as `ERROR_NETWORK` and cost one
    appointment a (retriable) attempt, not the rest of the run.
    """
    sent = 0
    for job in jobs:
        body = message_body(job.name, job.date, today)
        try:
            results = send_multicast(job.tokens, TITLE, body, push_data(job.appointment_id, job.date))
        except Exception:
            # `send_multicast` absorbs per-token network errors itself;
            # anything escaping it is unexpected and must still not take the
            # rest of the run down.
            logger.exception('Lỗi gửi nhắc lịch hẹn %s.', job.appointment_id)
            results = dict((token, SEND_ERROR) for token in job.tokens)
        if not results:
            return sent, False
        try:
            deactivate_dead(results)
            if log_attempt(job.appointment_id, today, results):
                sent += 1
        except Exception:
            # A deadlock while recording ONE attempt must not cost every
            # remaining appointment its reminder.
            logger.exception('Lỗi ghi nhật ký nhắc lịch hẹn %s.', job.appointment_id)
    return sent, True


class Command(BaseCommand):
    help = 'Gửi thông báo nhắc lịch hẹn sắp đến hạn (mỗi ngày cho tới hạn) qua FCM.'

    def handle(self, *args, **options):
        today = today_vn()
        jobs, skipped, due = collect_due(today)
        sent, configured = dispatch(jobs, today)

        if not configured:
            # Exit 0, not an exception: a host that was never given a service
            # account should say so once a day, not page anyone.
            self.stdout.write(self.style.WARNING(
                'Chưa cấu hình Firebase (FIREBASE_CREDENTIALS_PATH/JSON); không gửi được gì.'
            ))
        self.stdout.write(self.style.SUCCESS(
            '{}: {} lịch hẹn tới hạn, đã gửi {}, bỏ qua {} (đã gửi hôm nay).'.format(
                today, due, sent, skipped,
            )
        ))
        return None
