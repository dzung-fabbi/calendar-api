"""`manage.py remind_death_anniversary` -- who gets reminded, and when.

NO TEST HERE TOUCHES THE NETWORK. Every run goes through `run_on()`, which
patches `send_multicast` inside the command module; a test that reached
Firebase would be a test that fails in CI and charges someone money.

FIXTURE TREE (one clan, `gio_remind_before_days` = 3)

            cu (giỗ 5/2 âm)
           /               \\
    ong (giỗ 10/6)        bac (giỗ 3/3)
        |                     |
      toi (sống)            em (sống)

`owner` is bound to `toi`  -> direct line {ong, cu}
`viewer` is bound to `em`  -> direct line {bac, cu}   (ong is collateral: uncle)
`editor` is a member with a device but NO binding -> receives nothing.
"""

import datetime as dt
import json
import os
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

from giapha.models import (
    Clan,
    ClanMember,
    DeviceToken,
    GioFollow,
    GioNotificationLog,
    Person,
)
from giapha.services import fcm_auth
from giapha.services.fcm import DEAD_TOKEN_RESULTS, ERROR_NETWORK, RESULT_OK
from giapha.services.fcm_auth import FcmTransientError
from giapha.services.gio import gio_occurrences_in_range
from giapha.tests.factories import bind_member, build_clan_fixture, build_person

COMMAND = 'giapha.management.commands.remind_death_anniversary'
REMINDER_LOG = 'giapha.management.commands._gio_reminder_log'
AUTH = 'giapha.services.fcm_auth'
SERVICE_ACCOUNT = {'project_id': 'giapha-test', 'client_email': 'x@y.iam.gserviceaccount.com'}
REMIND_BEFORE = 3  # Clan.gio_remind_before_days default
# A fixed anchor, not `today`: a giỗ date derived from the clock would make
# these tests drift with the calendar.
ANCHOR = dt.date(2026, 1, 1)


def first_gio_after(day, month, start=ANCHOR):
    """The solar date of the first giỗ of `day/month` on or after `start`.

    Computed with the phase-5 service the command itself uses, because
    hard-coding a solar date would encode one particular lunar conversion into
    the test rather than the rule "three days before the giỗ".
    """
    window = gio_occurrences_in_range(day, month, start, start + dt.timedelta(days=420))
    return window[0].solar_date


def all_ok(tokens, *args, **kwargs):
    return dict((token, RESULT_OK) for token in tokens)


def run_on(today, side_effect=None):
    """Run the command as if `today` were today in Vietnam, FCM fully mocked.

    Returns `(send_multicast_mock, stdout)`.
    """
    out = StringIO()
    with mock.patch(COMMAND + '.today_vn', return_value=today), \
            mock.patch(COMMAND + '.send_multicast') as send:
        send.side_effect = side_effect or all_ok
        call_command('remind_death_anniversary', stdout=out)
    return send, out.getvalue()


def sent_tokens(send):
    """Every device token the command actually attempted, across all calls."""
    return set(token for call in send.call_args_list for token in call[0][0])


class RemindTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']
        cls.owner = cls.fixture['owner']
        cls.editor = cls.fixture['editor']
        cls.viewer = cls.fixture['viewer']

        cls.cu = build_person(
            cls.clan, ho_ten='Nguyễn Đình Cụ', generation=1,
            death_lunar_day=5, death_lunar_month=2,
        )
        cls.ong = build_person(
            cls.clan, ho_ten='Nguyễn Đình Ông', generation=2, father=cls.cu,
            death_lunar_day=10, death_lunar_month=6,
        )
        cls.bac = build_person(
            cls.clan, ho_ten='Nguyễn Đình Bác', generation=2, father=cls.cu,
            death_lunar_day=3, death_lunar_month=3,
        )
        cls.toi = build_person(cls.clan, ho_ten='Tôi', generation=3, father=cls.ong)
        cls.em = build_person(cls.clan, ho_ten='Em họ', generation=3, father=cls.bac)

        bind_member(cls.clan, cls.owner, cls.toi)
        bind_member(cls.clan, cls.viewer, cls.em)

        for user, token in (
            (cls.owner, 'tok-owner'), (cls.viewer, 'tok-viewer'), (cls.editor, 'tok-editor'),
        ):
            DeviceToken.objects.create(user=user, token=token, platform='android')

        cls.ong_gio = first_gio_after(10, 6)
        cls.cu_gio = first_gio_after(5, 2)
        cls.bac_gio = first_gio_after(3, 3)

    @staticmethod
    def remind_day(gio_date):
        return gio_date - dt.timedelta(days=REMIND_BEFORE)


class TargetDateTests(RemindTestCase):
    def test_sends_to_the_direct_line_on_the_target_date(self):
        send, _out = run_on(self.remind_day(self.ong_gio))

        self.assertEqual(send.call_count, 1)
        tokens, title, body, data = send.call_args[0]
        self.assertEqual(list(tokens), ['tok-owner'])
        self.assertEqual(title, 'Sắp đến ngày giỗ')
        self.assertIn('Còn 3 ngày nữa là giỗ Nguyễn Đình Ông (đời 2)', body)
        self.assertIn('10 tháng 6 âm lịch', body)
        self.assertIn(self.ong_gio.strftime('%d/%m/%Y'), body)
        self.assertEqual(
            data, {'type': 'gio', 'clan_id': self.clan.id, 'person_id': self.ong.id},
        )

        log = GioNotificationLog.objects.get()
        self.assertEqual(log.person_id, self.ong.id)
        self.assertEqual(log.user_id, self.owner.id)
        self.assertEqual(log.solar_date, self.ong_gio)
        self.assertEqual(log.status, 'sent')

    def test_nothing_the_day_before_or_the_day_after(self):
        for shift in (-1, 1):
            day = self.remind_day(self.ong_gio) + dt.timedelta(days=shift)
            send, _out = run_on(day)
            self.assertEqual(send.call_count, 0, 'sent on {}'.format(day))
        self.assertFalse(GioNotificationLog.objects.exists())

    def test_a_missing_generation_drops_the_doi_clause(self):
        """`generation` is nullable; "(đời None)" in a push would be worse."""
        Person.objects.filter(id=self.ong.id).update(generation=None)
        send, _out = run_on(self.remind_day(self.ong_gio))
        body = send.call_args[0][2]
        self.assertIn('giỗ Nguyễn Đình Ông —', body)
        self.assertNotIn('đời', body)

    def test_running_twice_in_one_day_sends_once(self):
        day = self.remind_day(self.ong_gio)
        run_on(day)
        send, _out = run_on(day)

        self.assertEqual(send.call_count, 0)
        self.assertEqual(GioNotificationLog.objects.count(), 1)


class RecipientTests(RemindTestCase):
    def test_a_member_without_a_binding_receives_nothing(self):
        """`editor` is in the clan and owns a device, but never said who they
        are in the tree -- so they have no direct line, and guessing one for
        them would be worse than silence.
        """
        send, _out = run_on(self.remind_day(self.cu_gio))
        self.assertNotIn('tok-editor', sent_tokens(send))
        self.assertFalse(GioNotificationLog.objects.filter(user=self.editor).exists())

    def test_a_collateral_relative_receives_nothing(self):
        """`ong` is `viewer`'s uncle, not their ancestor: same clan, off the
        line, no reminder. This is the spam rule the whole design exists for.
        """
        send, _out = run_on(self.remind_day(self.ong_gio))
        self.assertEqual(sent_tokens(send), {'tok-owner'})

    def test_a_shared_ancestor_reaches_both_lines(self):
        send, _out = run_on(self.remind_day(self.cu_gio))
        self.assertEqual(sent_tokens(send), {'tok-owner', 'tok-viewer'})

    def test_disabled_override_on_an_ancestor_suppresses_the_reminder(self):
        GioFollow.objects.create(person=self.ong, user=self.owner, enabled=False)
        send, _out = run_on(self.remind_day(self.ong_gio))
        self.assertEqual(send.call_count, 0)

    def test_enabled_override_on_a_non_ancestor_delivers(self):
        GioFollow.objects.create(person=self.bac, user=self.owner, enabled=True)
        send, _out = run_on(self.remind_day(self.bac_gio))
        self.assertIn('tok-owner', sent_tokens(send))

    def test_soft_deleted_clan_is_skipped(self):
        Clan.objects.filter(id=self.clan.id).update(is_deleted=True)
        send, _out = run_on(self.remind_day(self.ong_gio))
        self.assertEqual(send.call_count, 0)

    def test_soft_deleted_person_is_skipped(self):
        Person.objects.filter(id=self.ong.id).update(is_deleted=True)
        send, _out = run_on(self.remind_day(self.ong_gio))
        self.assertEqual(send.call_count, 0)


class DeliveryFailureTests(RemindTestCase):
    def test_missing_credentials_exits_cleanly(self):
        """`send_multicast` returns `{}` when no service account is
        configured. The command must warn and stop -- exit 0, no traceback,
        and nothing recorded as if it had been sent.
        """
        send, out = run_on(self.remind_day(self.cu_gio), side_effect=lambda *a, **kw: {})

        self.assertEqual(send.call_count, 1)  # stopped after the first signal
        self.assertFalse(GioNotificationLog.objects.exists())
        self.assertIn('Chưa cấu hình Firebase', out)
        self.assertTrue(DeviceToken.objects.get(token='tok-owner').is_active)

    def test_one_failing_recipient_does_not_stop_the_others(self):
        def flaky(tokens, *args, **kwargs):
            if 'tok-owner' in tokens:
                return {'tok-owner': ERROR_NETWORK}
            return all_ok(tokens)

        send, _out = run_on(self.remind_day(self.cu_gio), side_effect=flaky)

        self.assertEqual(send.call_count, 2)
        statuses = dict(GioNotificationLog.objects.values_list('user_id', 'status'))
        self.assertEqual(statuses[self.owner.id], 'failed')
        self.assertEqual(statuses[self.viewer.id], 'sent')

    def test_an_exception_from_the_sender_does_not_abort_the_run(self):
        def explode(tokens, *args, **kwargs):
            if 'tok-owner' in tokens:
                raise RuntimeError('boom')
            return all_ok(tokens)

        send, _out = run_on(self.remind_day(self.cu_gio), side_effect=explode)

        self.assertEqual(send.call_count, 2)
        self.assertTrue(GioNotificationLog.objects.filter(
            user=self.viewer, status='sent').exists())

    def test_one_bad_token_still_delivers_to_the_others(self):
        DeviceToken.objects.create(user=self.owner, token='tok-owner-2', platform='ios')

        def mixed(tokens, *args, **kwargs):
            return dict(
                (token, ERROR_NETWORK if token == 'tok-owner' else RESULT_OK)
                for token in tokens
            )

        send, _out = run_on(self.remind_day(self.ong_gio), side_effect=mixed)

        self.assertEqual(set(send.call_args[0][0]), {'tok-owner', 'tok-owner-2'})
        self.assertEqual(GioNotificationLog.objects.get(user=self.owner).status, 'sent')

    def test_dead_token_is_deactivated_but_a_network_error_is_not(self):
        DeviceToken.objects.create(user=self.owner, token='tok-owner-dead', platform='ios')

        def one_dead(tokens, *args, **kwargs):
            return dict(
                (token, DEAD_TOKEN_RESULTS[0] if token.endswith('dead') else ERROR_NETWORK)
                for token in tokens
            )

        run_on(self.remind_day(self.ong_gio), side_effect=one_dead)

        self.assertFalse(DeviceToken.objects.get(token='tok-owner-dead').is_active)
        # Transient: the device is probably fine, retry it tomorrow.
        self.assertTrue(DeviceToken.objects.get(token='tok-owner').is_active)


class QueryBudgetTests(TestCase):
    """One query per clan on a day with nothing due.

    The early `continue` in `_jobs_for_clan` is what holds this; a regression
    means the four resolution queries moved above it, multiplying a nightly
    job's cost by five for every clan in the database.
    """

    def test_one_query_per_clan_when_nothing_is_due(self):
        for i in range(3):
            Clan.objects.create(ten_ho='Họ {}'.format(i))

        # 1 for the clan list + 1 `deceased_with_lunar_death` per clan.
        with self.assertNumQueries(1 + 3):
            run_on(ANCHOR)


def all_failing(tokens, *args, **kwargs):
    """Every device transiently unreachable -- a `status='failed'` log row."""
    return dict((token, ERROR_NETWORK) for token in tokens)


class MembershipTests(RemindTestCase):
    """C1 -- an override must not outlive the membership that justified it."""

    def test_a_removed_member_stops_receiving_pushes(self):
        """Removing a member deletes the `ClanMember` row (and the binding),
        but leaves their `GioFollow` rows. Resolving overrides on
        `person__clan_id` alone kept pushing a deceased person's name to
        someone who now gets a 404 from every endpoint of that clan.
        """
        GioFollow.objects.create(person=self.ong, user=self.viewer, enabled=True)
        ClanMember.objects.filter(clan=self.clan, user=self.viewer).delete()

        send, _out = run_on(self.remind_day(self.ong_gio))

        self.assertEqual(sent_tokens(send), {'tok-owner'})
        self.assertFalse(GioNotificationLog.objects.filter(user=self.viewer).exists())
        # Non-destructive on purpose: the row survives for a rejoin.
        self.assertTrue(GioFollow.objects.filter(user=self.viewer, person=self.ong).exists())

    def test_rejoining_restores_the_kept_preferences(self):
        GioFollow.objects.create(person=self.ong, user=self.viewer, enabled=True)
        ClanMember.objects.filter(clan=self.clan, user=self.viewer).delete()
        ClanMember.objects.create(clan=self.clan, user=self.viewer, role='viewer')

        send, _out = run_on(self.remind_day(self.ong_gio))
        self.assertEqual(sent_tokens(send), {'tok-owner', 'tok-viewer'})


class SoftDeletedAncestorTests(RemindTestCase):
    """M1 -- a soft-deleted person must not sever the line above them."""

    def test_a_soft_deleted_parent_does_not_hide_the_grandparent(self):
        # `ong` sits between `toi` (owner's node) and `cu`.
        Person.objects.filter(id=self.ong.id).update(is_deleted=True)

        send, _out = run_on(self.remind_day(self.cu_gio))

        self.assertIn('tok-owner', sent_tokens(send))
        self.assertTrue(GioNotificationLog.objects.filter(
            person=self.cu, user=self.owner, status='sent').exists())

    def test_the_soft_deleted_person_still_generates_no_reminder(self):
        """Traversing THROUGH them must not mean notifying ABOUT them."""
        Person.objects.filter(id=self.ong.id).update(is_deleted=True)

        send, _out = run_on(self.remind_day(self.ong_gio))

        self.assertEqual(send.call_count, 0)
        self.assertFalse(GioNotificationLog.objects.filter(person=self.ong).exists())


class RetryTests(RemindTestCase):
    """H1 -- a person is due on exactly ONE calendar day a year, so a failed
    attempt that blocks the pair blocks it for the whole year.
    """

    def test_a_failed_send_is_retried_by_a_later_run(self):
        day = self.remind_day(self.ong_gio)

        run_on(day, side_effect=all_failing)
        self.assertEqual(GioNotificationLog.objects.get().status, 'failed')

        retry, _out = run_on(day)
        self.assertEqual(retry.call_count, 1, 'the failed pair was never retried')
        log = GioNotificationLog.objects.get()  # updated in place, not duplicated
        self.assertEqual(log.status, 'sent')
        self.assertEqual(log.error, '')

    def test_a_successful_send_is_never_repeated(self):
        day = self.remind_day(self.ong_gio)
        run_on(day)

        again, out = run_on(day)
        self.assertEqual(again.call_count, 0)
        self.assertEqual(GioNotificationLog.objects.count(), 1)
        self.assertIn('bỏ qua 1', out)

    def test_a_failure_for_one_recipient_does_not_retry_the_other(self):
        def only_owner_fails(tokens, *args, **kwargs):
            return all_failing(tokens) if 'tok-owner' in tokens else all_ok(tokens)

        day = self.remind_day(self.cu_gio)
        run_on(day, side_effect=only_owner_fails)

        retry, _out = run_on(day)
        self.assertEqual(sent_tokens(retry), {'tok-owner'})
        self.assertEqual(GioNotificationLog.objects.filter(status='sent').count(), 2)


class OkResponse(object):
    """The 200 `requests.post` result `fcm._send_one` expects."""

    status_code = 200

    def json(self):
        return {'name': 'projects/giapha-test/messages/1'}


class TransientAuthFailureTests(RemindTestCase):
    """H2 -- these run the REAL `send_multicast`; only `requests.post` and the
    OAuth mint step are faked, so the "no credentials" / "cannot mint right
    now" distinction is exercised end to end. Still no network.
    """

    def setUp(self):
        fcm_auth._token_cache.update({'key': None, 'value': None, 'expires_at': 0.0})
        self.addCleanup(
            fcm_auth._token_cache.update, {'key': None, 'value': None, 'expires_at': 0.0},
        )
        patcher = mock.patch.dict(
            os.environ, {'FIREBASE_CREDENTIALS_JSON': json.dumps(SERVICE_ACCOUNT)},
        )
        patcher.start()
        os.environ.pop('FIREBASE_CREDENTIALS_PATH', None)
        self.addCleanup(patcher.stop)

    def run_for_real(self, today, mint):
        out = StringIO()
        with mock.patch(COMMAND + '.today_vn', return_value=today), \
                mock.patch(AUTH + '._mint_token', side_effect=mint) as minted, \
                mock.patch('giapha.services.fcm.requests.post', return_value=OkResponse()) as post:
            call_command('remind_death_anniversary', stdout=out)
        return post, minted, out.getvalue()

    def test_a_mint_blip_does_not_abandon_the_remaining_recipients(self):
        """`cu`'s giỗ has two recipients. The first hits a transient OAuth
        failure; the second must still be attempted, and the operator must not
        be told Firebase is unconfigured.
        """
        post, minted, out = self.run_for_real(
            self.remind_day(self.cu_gio), [FcmTransientError('dns'), 'bearer-1'],
        )

        self.assertEqual(minted.call_count, 2)  # a failed mint is not cached
        self.assertEqual(post.call_count, 1)  # the second recipient was attempted
        self.assertNotIn('Chưa cấu hình Firebase', out)
        statuses = sorted(GioNotificationLog.objects.values_list('status', flat=True))
        self.assertEqual(statuses, ['failed', 'sent'])

    def test_the_abandoned_recipient_is_retried_by_the_next_run(self):
        day = self.remind_day(self.cu_gio)
        self.run_for_real(day, [FcmTransientError('dns'), 'bearer-1'])
        post, _minted, out = self.run_for_real(day, ['bearer-2'])

        self.assertEqual(post.call_count, 1)
        self.assertNotIn('Chưa cấu hình Firebase', out)
        self.assertEqual(GioNotificationLog.objects.filter(status='failed').count(), 0)
        self.assertEqual(GioNotificationLog.objects.filter(status='sent').count(), 2)

    def test_genuinely_absent_credentials_still_stop_the_run(self):
        """The other half of the same distinction: `{}` must keep meaning
        "not configured", warn once, and record nothing.
        """
        out = StringIO()
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch(COMMAND + '.today_vn', return_value=self.remind_day(self.cu_gio)), \
                mock.patch('giapha.services.fcm.requests.post') as post:
            call_command('remind_death_anniversary', stdout=out)

        post.assert_not_called()
        self.assertIn('Chưa cấu hình Firebase', out.getvalue())
        self.assertFalse(GioNotificationLog.objects.exists())


class LogFailureIsolationTests(RemindTestCase):
    """M2 -- a database error while recording ONE attempt must not cost every
    remaining recipient their reminder (per H1 there is no next day).
    """

    def test_a_log_error_does_not_abort_the_run(self):
        calls = []

        def one_log_explodes(job, user_id, results):
            calls.append(user_id)
            if len(calls) == 1:
                raise RuntimeError('deadlock')
            return True

        with mock.patch(COMMAND + '.log_attempt', side_effect=one_log_explodes):
            send, _out = run_on(self.remind_day(self.cu_gio))

        self.assertEqual(send.call_count, 2)
        self.assertEqual(len(calls), 2)

    def test_a_lost_race_is_not_counted_as_a_send(self):
        """M3 -- the `IntegrityError` branch means another process recorded
        this pair; the count the operator reads must not include a push this
        process did not make.
        """
        with mock.patch(
            REMINDER_LOG + '.GioNotificationLog.objects.update_or_create',
            side_effect=IntegrityError('duplicate'),
        ):
            _send, out = run_on(self.remind_day(self.ong_gio))

        self.assertIn('đã gửi 0', out)
