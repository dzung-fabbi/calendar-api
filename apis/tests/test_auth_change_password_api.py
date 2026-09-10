"""`POST /api/auth/change-password`, plus the end-to-end proof that accounts
created and recovered by this feature work with the `/api/auth/login` flow.

Real logins are used rather than `force_authenticate`, because the point of
half these tests is what happens to issued TOKENS -- which `force_authenticate`
bypasses entirely.
"""

import re

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apis.models import RefreshToken

CHANGE = '/api/auth/change-password'
LOGIN = '/api/auth/login'
REFRESH = '/api/auth/refresh'

EMAIL = 'nguoi.dung@example.com'
OLD_PASSWORD = 'MatKhauCu!2026'
NEW_PASSWORD = 'MatKhauMoi!2026'


def login(username=EMAIL, password=OLD_PASSWORD):
    return APIClient().post(LOGIN, {'username': username, 'password': password}, format='json')


class ChangePasswordAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username=EMAIL, email=EMAIL, password=OLD_PASSWORD,
        )

    def setUp(self):
        # Throttle buckets (`auth-login`, `auth-change-password`) live in the
        # shared process cache.
        cache.clear()
        mail.outbox = []
        self.user.set_password(OLD_PASSWORD)
        self.user.save()

    # -- helpers ---------------------------------------------------------

    def bearer(self, access_token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer {}'.format(access_token))
        return client

    def change(self, client, current=OLD_PASSWORD, new=NEW_PASSWORD):
        return client.post(
            CHANGE, {'current_password': current, 'new_password': new}, format='json',
        )

    # -- behaviour --------------------------------------------------------

    def test_changes_password_and_new_one_works_at_login(self):
        tokens = login().json()
        response = self.change(self.bearer(tokens['access_token']))
        self.assertEqual(200, response.status_code, response.content)

        self.assertEqual(401, login().status_code)
        self.assertEqual(200, login(password=NEW_PASSWORD).status_code)

    def test_every_token_is_revoked_including_the_callers_own(self):
        first = login().json()
        second = login().json()

        self.assertEqual(200, self.change(self.bearer(first['access_token'])).status_code)

        # Access tokens die through the `pwd` claim -- no table is consulted.
        for tokens in (first, second):
            self.assertEqual(401, self.bearer(tokens['access_token']).get('/api/me').status_code)
        self.assertEqual(0, RefreshToken.objects.filter(user=self.user).count())

    def test_revoked_refresh_token_cannot_mint_a_new_pair(self):
        """The refresh row is DELETED, not soft-revoked -- the predecessor's
        soft revoke was still honoured by its refresh grant inside a grace
        window, which is the bug this test exists to keep out."""
        tokens = login().json()
        self.change(self.bearer(tokens['access_token']))

        response = APIClient().post(
            REFRESH, {'refresh_token': tokens['refresh_token']}, format='json')
        self.assertEqual(401, response.status_code, response.content)

    def test_wrong_current_password_changes_nothing(self):
        client = self.bearer(login().json()['access_token'])
        response = self.change(client, current='SaiBetHet!2026')
        self.assertEqual(400, response.status_code)
        self.assertIn('current_password', response.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))

    def test_weak_new_password_changes_nothing(self):
        client = self.bearer(login().json()['access_token'])
        response = self.change(client, new='123456')
        self.assertEqual(400, response.status_code)
        self.assertIn('new_password', response.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))

    def test_new_password_equal_to_current_is_rejected(self):
        client = self.bearer(login().json()['access_token'])
        response = self.change(client, new=OLD_PASSWORD)
        self.assertEqual(400, response.status_code)
        self.assertIn('new_password', response.json())

    def test_unauthenticated_is_401(self):
        self.assertEqual(401, APIClient().post(
            CHANGE, {'current_password': OLD_PASSWORD, 'new_password': NEW_PASSWORD},
            format='json').status_code)

    def test_unusable_password_logs_the_caller_out(self):
        client = self.bearer(login().json()['access_token'])
        self.user.set_unusable_password()
        self.user.save()
        response = self.change(client)
        # `set_unusable_password` rewrote the hash, so the `pwd` claim no longer
        # matches: the caller is logged out before the view ever runs.
        self.assertEqual(401, response.status_code)


class RegisterThenLoginTests(TestCase):
    """The whole product flow: register -> log in -> read `me`.

    This is the test that proves registration produces an account the login
    endpoint accepts. If only one test in this feature survives, it should be
    this one.
    """

    def setUp(self):
        cache.clear()
        mail.outbox = []

    def test_register_then_login_then_read_me(self):
        registered = APIClient().post('/api/auth/register', {
            'email': EMAIL, 'password': OLD_PASSWORD,
            'first_name': 'An', 'last_name': 'Nguyễn',
        }, format='json')
        self.assertEqual(201, registered.status_code, registered.content)

        token_response = login()
        self.assertEqual(200, token_response.status_code, token_response.content)

        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION='Bearer {}'.format(token_response.json()['access_token']))
        me = client.get('/api/me')
        self.assertEqual(200, me.status_code, me.content)
        self.assertEqual(EMAIL, me.json()['data']['email'])

    def test_forgotten_password_recovers_login(self):
        APIClient().post('/api/auth/register', {
            'email': EMAIL, 'password': OLD_PASSWORD}, format='json')

        APIClient().post('/api/auth/forgot-password', {'email': EMAIL}, format='json')
        code = re.search(r'\b(\d{6})\b', mail.outbox[-1].body).group(1)
        reset = APIClient().post('/api/auth/reset-password', {
            'email': EMAIL, 'code': code, 'new_password': NEW_PASSWORD}, format='json')
        self.assertEqual(200, reset.status_code, reset.content)

        self.assertEqual(401, login().status_code)
        self.assertEqual(200, login(password=NEW_PASSWORD).status_code)
