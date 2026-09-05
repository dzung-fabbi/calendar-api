"""Find the appointments whose reminder falls due today.

INCOMPLETE: the command previously built this queryset and then discarded it,
so it has never delivered a reminder. What delivery should look like (email,
push, something else) is not recorded anywhere in the codebase, so this reports
what is due and leaves the delivery step to be specified. See the handover
notes.
"""

import logging

from django.core.management.base import BaseCommand
from django.db.models import DateField, ExpressionWrapper, F
from django.utils import timezone

from apis.models import AppointmentDate

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'List the appointments whose reminder is due today'

    def handle(self, *args, **options):
        today = timezone.localdate()

        # Remind `before_days` ahead of the appointment: the reminder is due
        # when appointment_date - before_days == today, i.e. when
        # appointment_date == today + before_days.
        due_on = ExpressionWrapper(
            F('date') - F('before_days'), output_field=DateField()
        )
        due = (
            AppointmentDate.objects
            .annotate(remind_on=due_on)
            .filter(remind_on=today)
            .select_related('user')
        )

        count = 0
        for appointment in due:
            count += 1
            logger.info(
                'Reminder due: "%s" on %s for user %s',
                appointment.name, appointment.date,
                appointment.user_id or 'unassigned',
            )

        self.stdout.write('{}: {} reminder(s) due'.format(today, count))
        return None
