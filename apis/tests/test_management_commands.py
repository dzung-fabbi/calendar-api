"""`manage.py remind_appointment_date` -- who is pushed, on which days.

NO TEST HERE TOUCHES THE NETWORK: every run goes through `run_on()`, which
patches `send_multicast` inside the command module.

The reminder is DAILY. With `before_days=3` and an appointment on D, the
owner is pushed on D-3, D-2, D-1 and D; never on D-4 or D+1.
"""

import datetime as dt
from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apis.models import AppointmentDate, AppointmentReminderLog
from apis.services.appointment_remind import message_body, push_data
from giapha.models import DeviceToken
from giapha.services.fcm import ERROR_NETWORK, ERROR_UNREGISTERED, RESULT_OK

COMMAND = 'apis.management.commands.remind_appointment_date'
# A fixed anchor, not the clock: dates derived from `today` would make these
# tests drift with the calendar.
DUE = dt.date(2026, 10, 1)


def all_ok(tokens, *args, **kwargs):
    return dict((token, RESULT_OK) for token in tokens)


def run_on(today, side_effect=None):
    """Run the command as if `today` were today in Vietnam, FCM fully mocked."""
    out = StringIO()
    with mock.patch(COMMAND + '.today_vn', return_value=today), \
            mock.patch(COMMAND + '.send_multicast') as send:
        send.side_effect = side_effect or all_ok
        call_command('remind_appointment_date', stdout=out)
    return send, out.getvalue()


def sent_tokens(send):
    return set(token for call in send.call_args_list for token in call[0][0])


class RemindAppointmentDateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='owner', password='pw')
        cls.other = User.objects.create_user(username='other', password='pw')
        DeviceToken.objects.create(user=cls.owner, token='tok-owner', platform='android')
        DeviceToken.objects.create(user=cls.owner, token='tok-owner-2', platform='ios')
        cls.dang_kiem = AppointmentDate.objects.create(
            name='Đăng kiểm xe', date=DUE, before_days=dt.timedelta(days=3), user=cls.owner,
        )

    def test_pushes_every_day_from_the_lead_time_to_the_date_itself(self):
        for offset in (3, 2, 1, 0):
            send, out = run_on(DUE - dt.timedelta(days=offset))
            self.assertEqual({'tok-owner', 'tok-owner-2'}, sent_tokens(send), offset)
            self.assertIn('đã gửi 1', out)

    def test_nothing_before_the_window_or_after_the_date(self):
        for today in (DUE - dt.timedelta(days=4), DUE + dt.timedelta(days=1)):
            send, _out = run_on(today)
            send.assert_not_called()

    def test_zero_before_days_reminds_on_the_day_only(self):
        AppointmentDate.objects.create(name='Hôm nay', date=DUE, user=self.owner)
        send, _out = run_on(DUE - dt.timedelta(days=1))
        self.assertEqual(1, send.call_count)  # only `dang_kiem`
        send, _out = run_on(DUE)
        self.assertEqual(2, send.call_count)

    def test_message_and_payload(self):
        send, _out = run_on(DUE - dt.timedelta(days=2))
        _tokens, title, body, data = send.call_args[0]
        self.assertEqual('Sắp đến hạn lịch hẹn', title)
        self.assertEqual('Còn 2 ngày nữa đến hạn: Đăng kiểm xe (01/10/2026).', body)
        self.assertEqual(
            {'type': 'appointment', 'appointment_id': str(self.dang_kiem.id), 'date': '2026-10-01'},
            data,
        )

    def test_running_twice_in_one_day_sends_once(self):
        run_on(DUE)
        send, out = run_on(DUE)
        send.assert_not_called()
        self.assertIn('bỏ qua 1', out)
        self.assertEqual(
            1, AppointmentReminderLog.objects.filter(appointment=self.dang_kiem).count(),
        )

    def test_the_next_day_sends_again(self):
        run_on(DUE - dt.timedelta(days=1))
        send, _out = run_on(DUE)
        self.assertEqual(1, send.call_count)
        self.assertEqual(2, AppointmentReminderLog.objects.count())

    def test_owner_without_a_device_is_skipped_without_a_log_row(self):
        AppointmentDate.objects.create(
            name='Không có máy', date=DUE, before_days=dt.timedelta(days=3), user=self.other,
        )
        send, out = run_on(DUE)
        self.assertEqual({'tok-owner', 'tok-owner-2'}, sent_tokens(send))
        self.assertEqual(1, AppointmentReminderLog.objects.count())
        self.assertIn('2 lịch hẹn tới hạn, đã gửi 1', out)

    def test_unassigned_or_dateless_rows_are_ignored(self):
        AppointmentDate.objects.create(name='Vô chủ', date=DUE)
        AppointmentDate.objects.create(name='Không ngày', date=None, user=self.owner)
        send, _out = run_on(DUE)
        self.assertEqual(1, send.call_count)

    def test_a_failed_send_is_retried_by_a_rerun_the_same_day(self):
        def all_fail(tokens, *args, **kwargs):
            return dict((token, ERROR_NETWORK) for token in tokens)

        _send, out = run_on(DUE, side_effect=all_fail)
        self.assertIn('đã gửi 0', out)
        log = AppointmentReminderLog.objects.get(appointment=self.dang_kiem)
        self.assertEqual('failed', log.status)

        send, out = run_on(DUE)
        self.assertEqual(1, send.call_count)
        log.refresh_from_db()
        self.assertEqual('sent', log.status)

    def test_dead_token_is_deactivated_but_a_network_error_is_not(self):
        def mixed(tokens, *args, **kwargs):
            return {'tok-owner': ERROR_UNREGISTERED, 'tok-owner-2': ERROR_NETWORK}

        run_on(DUE, side_effect=mixed)
        self.assertFalse(DeviceToken.objects.get(token='tok-owner').is_active)
        self.assertTrue(DeviceToken.objects.get(token='tok-owner-2').is_active)

    def test_missing_credentials_exits_cleanly(self):
        send, out = run_on(DUE, side_effect=lambda *a, **k: {})
        self.assertIn('Chưa cấu hình Firebase', out)
        self.assertEqual(0, AppointmentReminderLog.objects.count())

    def test_an_exception_from_the_sender_does_not_abort_the_run(self):
        AppointmentDate.objects.create(
            name='Bảo hiểm', date=DUE, before_days=dt.timedelta(days=3), user=self.owner,
        )
        calls = []

        def first_raises(tokens, *args, **kwargs):
            calls.append(tokens)
            if len(calls) == 1:
                raise RuntimeError('boom')
            return all_ok(tokens)

        _send, out = run_on(DUE, side_effect=first_raises)
        self.assertEqual(2, len(calls))
        self.assertIn('đã gửi 1', out)
        self.assertEqual(
            {'failed', 'sent'},
            set(AppointmentReminderLog.objects.values_list('status', flat=True)),
        )

    def test_one_query_on_a_quiet_day(self):
        # Nothing due: the token and log lookups are skipped, not run empty.
        with self.assertNumQueries(1):
            run_on(DUE + dt.timedelta(days=1))

    def test_three_reads_before_the_first_send(self):
        with self.assertNumQueries(3):
            with mock.patch(COMMAND + '.today_vn', return_value=DUE), \
                    mock.patch(COMMAND + '.send_multicast', side_effect=lambda *a, **k: {}):
                call_command('remind_appointment_date', stdout=StringIO())


class MessageBodyTests(SimpleTestCase):
    def test_counts_down_to_the_day_itself(self):
        self.assertEqual(
            'Còn 3 ngày nữa đến hạn: Đăng kiểm xe (01/10/2026).',
            message_body('Đăng kiểm xe', DUE, DUE - dt.timedelta(days=3)),
        )
        self.assertEqual(
            'Hôm nay đến hạn: Đăng kiểm xe (01/10/2026).', message_body('Đăng kiểm xe', DUE, DUE),
        )

    def test_payload_is_all_strings(self):
        for value in push_data(7, DUE).values():
            self.assertIsInstance(value, str)
