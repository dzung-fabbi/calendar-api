"""The two ORM writes behind `remind_death_anniversary.dispatch`.

Split out of the command to keep both files under the 200-line rule; the
leading underscore keeps Django's command discovery from treating this module
as a command of its own.

Deliberately NOT in `services/`: both functions write through the ORM, and
`docs/code-standards.md` -> Layering keeps `services/` free of it.
"""

import logging

from django.db import IntegrityError, transaction

from giapha.models import DeviceToken, GioNotificationLog
from giapha.services.fcm import DEAD_TOKEN_RESULTS, RESULT_OK

logger = logging.getLogger(__name__)

ERROR_MAX_LENGTH = 255  # GioNotificationLog.error
# Reported for every token of a send that raised out of `send_multicast`.
SEND_ERROR = 'send_error'


def deactivate_dead(results):
    """Retire the tokens FCM called dead. The ORM write lives here, never in
    `services/fcm.py` (Layering); `ERROR_NETWORK` and 5xx are transient, so
    those tokens stay active for tomorrow.
    """
    dead = [token for token, result in results.items() if result in DEAD_TOKEN_RESULTS]
    if dead:
        DeviceToken.objects.filter(token__in=dead).update(is_active=False)


def log_attempt(job, user_id, results):
    """Record the attempt; True when at least one device took it.

    A `failed` row does NOT block a retry -- `notified_pairs` reads `sent`
    rows only. A person is due on exactly ONE calendar day a year, so
    "tomorrow's run covers them" is false and re-running the command after an
    outage is the only retry there is. `update_or_create` on the
    `unique_together` triple lets that retry overwrite the failed row.
    """
    errors = [result for result in results.values() if result != RESULT_OK]
    delivered = len(errors) < len(results)
    try:
        # Savepoint: without it an IntegrityError would poison the surrounding
        # atomic block (a `TestCase`, or any future transactional caller).
        with transaction.atomic():
            GioNotificationLog.objects.update_or_create(
                person_id=job.person_id, user_id=user_id, solar_date=job.solar_date,
                defaults={
                    'status': 'sent' if delivered else 'failed',
                    'error': '' if delivered else ', '.join(errors)[:ERROR_MAX_LENGTH],
                },
            )
    except IntegrityError:
        # A concurrent run claimed this pair between `notified_pairs` and here.
        # NOT delivered: "đã gửi N" must not count a push this process did not
        # make.
        logger.info('Đã có nhật ký nhắc giỗ person=%s user=%s.', job.person_id, user_id)
        return False
    return delivered
