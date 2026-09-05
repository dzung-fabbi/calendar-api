"""Tests for the management commands."""

import datetime as dt
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apis.models import AppointmentDate


class RemindAppointmentDateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='reminder', password='pw')
        today = timezone.localdate()
        # Due today: three days before an appointment three days out.
        cls.due = AppointmentDate.objects.create(
            name='Sap toi', date=today + dt.timedelta(days=3),
            before_days=dt.timedelta(days=3), user=cls.user,
        )
        # Not due: the reminder for this one fired yesterday.
        AppointmentDate.objects.create(
            name='Da qua', date=today + dt.timedelta(days=2),
            before_days=dt.timedelta(days=3), user=cls.user,
        )
        # Not due: still a week of lead time to go.
        AppointmentDate.objects.create(
            name='Con xa', date=today + dt.timedelta(days=10),
            before_days=dt.timedelta(days=3), user=cls.user,
        )

    def test_reports_only_the_appointments_due_today(self):
        out = StringIO()
        call_command('remind_appointment_date', stdout=out)
        self.assertIn('1 reminder(s) due', out.getvalue())

    def test_zero_before_days_reminds_on_the_day_itself(self):
        AppointmentDate.objects.all().delete()
        AppointmentDate.objects.create(
            name='Hom nay', date=timezone.localdate(), user=self.user,
        )
        out = StringIO()
        call_command('remind_appointment_date', stdout=out)
        self.assertIn('1 reminder(s) due', out.getvalue())
