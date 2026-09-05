"""`python manage.py remind_death_anniversary` -- nhắc giỗ hằng ngày qua FCM.

Run once a day by cron (see `docs/deployment-guide.md`): there is no Celery
here and one job a day does not justify adding it.

TWO HALVES: `collect_due(today)` does every read and every computation,
returning `GioJob`s whose recipients are already resolved down to device
tokens; `dispatch(jobs)` is the only half that touches the network (its two
ORM-write helpers live in `_gio_reminder_log.py`). That is
what lets `tests/test_remind_command.py` assert *who* would be reminded
without mocking anything. The arithmetic lives in `services/gio_remind.py`.

QUERY BUDGET -- 1 PER CLAN ON A QUIET DAY: `deceased_with_lunar_death` runs
first and the clan is abandoned before the other four queries whenever
nothing is due, which is almost every clan on almost every day. Do NOT
reorder that early exit: at 1.000 clans it is the difference between ~1.000
and ~5.000 queries for a job nobody is waiting on.

TIMEZONE: `services.gio.today_vn()`, never `timezone.localdate()`.
`settings.TIME_ZONE` is UTC with `USE_TZ=True`, so a cron firing at 05:00
Vietnam time would compute *yesterday* and send every reminder a day off.
"""

import datetime as dt
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from giapha.management.commands._gio_reminder_log import (
    SEND_ERROR,
    deactivate_dead,
    log_attempt,
)
from giapha.models import Clan
from giapha.selectors.gio import deceased_with_lunar_death
from giapha.selectors.gio_follow import (
    active_tokens_for,
    binding_map,
    notified_pairs,
    overrides_for_clan,
)
from giapha.selectors.person import clan_edges_all
from giapha.services.fcm import send_multicast
from giapha.services.gio import today_vn
from giapha.services.gio_follow import followers_by_person
from giapha.services.gio_remind import TITLE, GioJob, due_rows, message_body

logger = logging.getLogger(__name__)

def _jobs_for_clan(clan, today):
    target = today + dt.timedelta(days=clan.gio_remind_before_days)

    rows, truncated = deceased_with_lunar_death(clan.id, settings.MAX_CLAN_PERSONS)
    if truncated:
        logger.warning(
            'Dòng họ %s vượt MAX_CLAN_PERSONS; phần đuôi không được xét nhắc giỗ.', clan.id,
        )
    due = due_rows(rows, target)
    if not due:
        return []  # THE early exit -- see the module docstring's query budget.

    # `clan_edges_all`, NOT `clan_edges`: the walk must pass THROUGH a
    # soft-deleted ancestor or it severs every ancestor above them. Nobody is
    # notified ABOUT one -- `deceased_with_lunar_death` excludes them from `due`.
    edges = clan_edges_all(clan.id)
    bindings = binding_map(clan.id)
    overrides = overrides_for_clan(clan.id)
    followers = followers_by_person(
        edges, bindings, overrides, set(row['id'] for row, _occurrence in due),
    )
    tokens = active_tokens_for(set().union(*followers.values()) if followers else ())

    jobs = []
    for row, occurrence in due:
        # A follower with no active device is dropped rather than logged as a
        # failure: nothing was attempted, so nothing is owed a row.
        recipients = dict(
            (user_id, tokens[user_id])
            for user_id in followers.get(row['id'], ())
            if tokens.get(user_id)
        )
        if not recipients:
            continue
        jobs.append(GioJob(
            clan_id=clan.id, person_id=row['id'], ho_ten=row['ho_ten'],
            generation=row['generation'], solar_date=occurrence.solar_date,
            lunar_day=occurrence.day, lunar_month=occurrence.month,
            days_left=(occurrence.solar_date - today).days, recipients=recipients,
        ))
    return jobs


def collect_due(today):
    """Every reminder due `today`, recipients and device tokens resolved."""
    jobs = []
    clans = Clan.objects.filter(is_deleted=False).only('id', 'gio_remind_before_days')
    for clan in clans:
        try:
            jobs.extend(_jobs_for_clan(clan, today))
        except Exception:
            # Deliberately broad, against `docs/code-standards.md` -> Errors:
            # this is a nightly batch, not a request. One clan holding a corrupt
            # row must cost that clan its reminders, not the other 999 clans
            # theirs. The traceback still reaches the logger.
            logger.exception('Bỏ qua dòng họ %s khi thu thập nhắc giỗ.', clan.id)
    return jobs


def dispatch(jobs):
    """Send `jobs`. Returns `(sent, skipped, configured)`.

    `configured` is False ONLY when `send_multicast` answered `{}` to a
    NON-EMPTY token list, which it reserves strictly for "no usable service
    account". A transient failure minting the OAuth token arrives as per-token
    `ERROR_NETWORK` instead, so it costs one recipient a (retriable) attempt
    rather than abandoning the run and mislabelling it "not configured".
    """
    already = notified_pairs(
        set(job.person_id for job in jobs), set(job.solar_date for job in jobs),
    )
    sent = 0
    skipped = 0
    for job in jobs:
        body = message_body(job)
        data = {'type': 'gio', 'clan_id': job.clan_id, 'person_id': job.person_id}
        for user_id, tokens in job.recipients.items():
            if (job.person_id, user_id, job.solar_date) in already:
                skipped += 1
                continue
            if not tokens:
                continue  # Keeps `{}` below reserved for "no credentials".
            try:
                results = send_multicast(tokens, TITLE, body, data)
            except Exception:
                # `send_multicast` absorbs per-token network errors itself;
                # anything escaping it is unexpected and must still not take
                # the rest of the run down.
                logger.exception('Lỗi gửi nhắc giỗ person=%s user=%s.', job.person_id, user_id)
                results = dict((token, SEND_ERROR) for token in tokens)
            if not results:
                return sent, skipped, False
            try:
                deactivate_dead(results)
                if log_attempt(job, user_id, results):
                    sent += 1
            except Exception:
                # Same reasoning as `collect_due`'s broad catch: a deadlock
                # while recording ONE attempt must not cost every remaining
                # recipient their reminder -- there is no next day for them.
                logger.exception(
                    'Lỗi ghi nhật ký nhắc giỗ person=%s user=%s.', job.person_id, user_id,
                )
    return sent, skipped, True


class Command(BaseCommand):
    help = 'Gửi thông báo nhắc ngày giỗ sắp tới cho những người theo dõi.'

    def handle(self, *args, **options):
        today = today_vn()
        jobs = collect_due(today)
        sent, skipped, configured = dispatch(jobs)

        if not configured:
            # Exit 0, not an exception: a host that was never given a service
            # account should say so once a day, not page anyone.
            self.stdout.write(self.style.WARNING(
                'Chưa cấu hình Firebase (FIREBASE_CREDENTIALS_PATH/JSON); không gửi được gì.'
            ))
        self.stdout.write(self.style.SUCCESS(
            '{}: {} lượt nhắc giỗ, đã gửi {}, bỏ qua {} (đã gửi trước đó).'.format(
                today, len(jobs), sent, skipped,
            )
        ))
        return None
