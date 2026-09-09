"""The forgot-password / verify-otp / reset-password flow.

The assertions that matter most here are the NEGATIVE ones: that an unknown
address is indistinguishable from a known one, and that a code cannot be
guessed. Those are the properties an unauthenticated endpoint lives or dies by.
"""

import re
from datetime import timedelta
from smtplib import SMTPException
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apis.models import PasswordResetCode

FORGOT = '/api/auth/forgot-password'
VERIFY = '/api/auth/verify-otp'
RESET = '/api/auth/reset-password'

EMAIL = 'nguoi.dung@example.com'
OLD_PASSWORD = 'MatKhauCu!2026'
NEW_PASSWORD = 'MatKhauMoi!2026'


class PasswordResetFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.client = APIClient()
        self.user = User.objects.create_user(
            username=EMAIL, email=EMAIL, password=OLD_PASSWORD,
        )

    # -- helpers ---------------------------------------------------------

    def request_code(self, email=EMAIL):
        return self.client.post(FORGOT, {'email': email}, format='json')

    def sent_code(self):
        """The 6-digit code out of the most recent email."""
        return re.search(r'\b(\d{6})\b', mail.outbox[-1].body).group(1)

    def issue(self):
        self.request_code()
        return self.sent_code()

    def reset(self, code, password=NEW_PASSWORD):
        return self.client.post(
            RESET, {'email': EMAIL, 'code': code, 'new_password': password}, format='json',
        )

    # -- requesting a code ------------------------------------------------

    def test_request_sends_one_mail_and_stores_one_code(self):
        response = self.request_code()
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(1, len(mail.outbox))
        self.assertEqual([EMAIL], mail.outbox[0].to)
        self.assertEqual(1, PasswordResetCode.objects.filter(user=self.user).count())

    def test_code_is_never_stored_in_plaintext_nor_returned(self):
        response = self.request_code()
        code = self.sent_code()
        row = PasswordResetCode.objects.get(user=self.user)
        self.assertNotEqual(code, row.code_hash)
        self.assertEqual(64, len(row.code_hash))
        self.assertNotIn(code, response.content.decode())

    def test_unknown_email_is_byte_identical_and_sends_nothing(self):
        baseline = self.request_code()
        mail.outbox = []
        response = self.request_code(email='khong.ton.tai@example.com')
        self.assertEqual(baseline.status_code, response.status_code)
        self.assertEqual(baseline.content, response.content)
        self.assertEqual(0, len(mail.outbox))

    def test_inactive_user_is_byte_identical_and_sends_nothing(self):
        """A banned account must not be recoverable through mailbox
        possession -- that would make this an account-reactivation bypass."""
        baseline = self.request_code()
        mail.outbox = []
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        response = self.request_code()
        self.assertEqual(baseline.content, response.content)
        self.assertEqual(0, len(mail.outbox))

    def test_smtp_failure_is_still_a_normal_200(self):
        """A 5xx here would be an enumeration oracle: a send is only ATTEMPTED
        for addresses that exist, so its failure reveals that they do."""
        baseline = self.request_code()
        with mock.patch('apis.services.mailer.send_mail', side_effect=SMTPException):
            response = self.request_code()
        self.assertEqual(baseline.status_code, response.status_code)
        self.assertEqual(baseline.content, response.content)

    def test_new_request_invalidates_the_previous_code(self):
        first = self.issue()
        self.issue()
        self.assertEqual(400, self.reset(first).status_code)

    def test_per_user_request_cap_stops_at_three_per_hour(self):
        for _ in range(3):
            self.request_code()
        mail.outbox = []
        response = self.request_code()
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(mail.outbox))

    # -- verifying --------------------------------------------------------

    def test_verify_accepts_the_code_without_consuming_it(self):
        code = self.issue()
        self.assertEqual(200, self.client.post(
            VERIFY, {'email': EMAIL, 'code': code}, format='json').status_code)
        self.assertEqual(200, self.reset(code).status_code)

    def test_verify_counts_a_wrong_guess(self):
        self.issue()
        self.client.post(VERIFY, {'email': EMAIL, 'code': '000000'}, format='json')
        self.assertEqual(1, PasswordResetCode.objects.get(user=self.user).attempts)

    # -- resetting --------------------------------------------------------

    def test_reset_changes_the_password_and_consumes_the_code(self):
        code = self.issue()
        self.assertEqual(200, self.reset(code).status_code)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertIsNotNone(PasswordResetCode.objects.get(user=self.user).used_at)

    def test_code_cannot_be_replayed(self):
        code = self.issue()
        self.reset(code)
        self.assertEqual(400, self.reset(code, 'MatKhauKhac!2026').status_code)

    def test_expired_code_is_rejected(self):
        code = self.issue()
        PasswordResetCode.objects.filter(user=self.user).update(
            expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(400, self.reset(code).status_code)

    def test_code_dies_after_five_wrong_attempts(self):
        code = self.issue()
        for _ in range(5):
            self.reset('000000')
        # Even the CORRECT code no longer works: lockout is per code.
        self.assertEqual(400, self.reset(code).status_code)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))

    def test_weak_new_password_neither_consumes_nor_burns_the_code(self):
        code = self.issue()
        self.assertEqual(400, self.reset(code, '123456').status_code)
        row = PasswordResetCode.objects.get(user=self.user)
        self.assertEqual(0, row.attempts)
        self.assertIsNone(row.used_at)
        self.assertEqual(200, self.reset(code).status_code)

    def test_another_users_code_is_rejected(self):
        other = User.objects.create_user(
            username='khac@example.com', email='khac@example.com', password=OLD_PASSWORD)
        self.issue()
        other_code = '000000'
        response = self.client.post(
            RESET,
            {'email': other.email, 'code': other_code, 'new_password': NEW_PASSWORD},
            format='json',
        )
        self.assertEqual(400, response.status_code)

    def test_failure_bodies_are_indistinguishable(self):
        """Wrong / expired / unknown-account must not be tellable apart."""
        code = self.issue()
        wrong = self.reset('000000')

        PasswordResetCode.objects.filter(user=self.user).update(
            expires_at=timezone.now() - timedelta(minutes=1))
        expired = self.reset(code)

        unknown = self.client.post(
            RESET,
            {'email': 'khong.ton.tai@example.com', 'code': '000000',
             'new_password': NEW_PASSWORD},
            format='json',
        )
        self.assertEqual(wrong.content, expired.content)
        self.assertEqual(wrong.content, unknown.content)

    def test_legacy_unusable_password_account_can_reset(self):
        """An account carrying `set_unusable_password()` cannot authenticate by
        password at all. Reset is its ONLY recovery path, so it must not be
        gated on `has_usable_password()`."""
        self.user.set_unusable_password()
        self.user.save()
        self.assertFalse(self.user.has_usable_password())

        code = self.issue()
        self.assertEqual(200, self.reset(code).status_code)
        self.user.refresh_from_db()
        self.assertTrue(self.user.has_usable_password())
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
