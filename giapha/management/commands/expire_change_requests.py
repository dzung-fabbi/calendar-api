"""Daily housekeeping for change requests (đề xuất thay đổi).

    python manage.py expire_change_requests

Run from the same daily cron as `remind_death_anniversary`. Idempotent:

* pending for >= 30 days -> `expired`, proposer pushed (they may resend);
* pending for >= 7 days and never reminded -> reviewers pushed once,
  `reminded_at` stamped so a second run the same day (or any later day)
  never reminds again.

Expiry runs first so a 30-day-old proposal is never also "reminded".
"""

import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from giapha.models import ChangeRequest
from giapha.notifications import push_to_users
from giapha.selectors.change_request import pending_created_before, reviewer_members

REMIND_AFTER_DAYS = 7
EXPIRE_AFTER_DAYS = 30


def expire_old(now):
    expired = pending_created_before(now - datetime.timedelta(days=EXPIRE_AFTER_DAYS))
    count = 0
    for cr in expired:
        # Guarded update: an approval committing at the same moment wins.
        if not ChangeRequest.objects.filter(id=cr.id, status='pending').update(status='expired', reviewed_at=now):
            continue
        count += 1
        push_to_users(
            [cr.proposer_id], 'Đề xuất đã hết hạn',
            'Đề xuất sửa gia phả của bạn đã quá 30 ngày chưa được duyệt. Bạn có thể gửi lại.',
            {'type': 'change_request_expired', 'clan_id': cr.clan_id, 'change_request_id': cr.id},
        )
    return count


def remind_reviewers(now):
    due = [cr for cr in pending_created_before(now - datetime.timedelta(days=REMIND_AFTER_DAYS)) if cr.reminded_at is None]
    by_clan = {}
    for cr in due:
        by_clan.setdefault(cr.clan_id, []).append(cr.id)
    for clan_id, cr_ids in by_clan.items():
        push_to_users(
            [member.user_id for member in reviewer_members(clan_id)],
            'Đề xuất chờ duyệt đã lâu',
            'Có {} đề xuất sửa gia phả chờ duyệt hơn {} ngày.'.format(len(cr_ids), REMIND_AFTER_DAYS),
            {'type': 'change_request_reminder', 'clan_id': clan_id},
        )
        ChangeRequest.objects.filter(id__in=cr_ids).update(reminded_at=now)
    return len(due)


class Command(BaseCommand):
    help = 'Nhắc người duyệt đề xuất chờ 7 ngày, hết hạn đề xuất chờ 30 ngày.'

    def handle(self, *args, **options):
        now = timezone.now()
        expired = expire_old(now)
        reminded = remind_reviewers(now)
        self.stdout.write('Đã hết hạn {} đề xuất, nhắc {} đề xuất.'.format(expired, reminded))
