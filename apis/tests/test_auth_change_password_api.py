"""`POST /api/auth/change-password`, plus the end-to-end proof that accounts
created and recovered by this feature work with the UNTOUCHED `/auth/token`
login flow.

Real OAuth2 `Application` rows are used rather than `force_authenticate`,
because the point of half these tests is what happens to issued TOKENS -- which
`force_authenticate` bypasses entirely. Same setup as
`giapha/tests/test_auth_token_endpoints.py`; note `client_secret` is hashed on
save, so the plaintext has to be kept in a constant.
"""

import re
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from oauth2_provider.models import Application, get_access_token_model, get_refresh_token_model
from rest_framework.test import APIClient

CHANGE = '/api/auth/change-password'
TOKEN_URL = '/auth/token'
FORM = 'application/x-www-form-urlencoded'

EMAIL = 'nguoi.dung@example.com'
OLD_PASSWORD = 'MatKhauCu!2026'
NEW_PASSWORD = 'MatKhauMoi!2026'
RAW_SECRET = 'test-client-secret'


class ChangePasswordAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username=EMAIL, email=EMAIL, password=OLD_PASSWORD,
        )
        app = Application.objects.create(
            name='test-client',
            user=cls.user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_PASSWORD,
            client_secret=RAW_SECRET,
        )
        cls.client_id = app.client_id

    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.user.set_password(OLD_PASSWORD)
        self.user.save()

    # -- helpers ---------------------------------------------------------

    def login(self, password=OLD_PASSWORD, username=EMAIL):
        return self.client.post(TOKEN_URL, data=urlencode({
            'grant_type': 'password',
            'username': username,
            'password': password,
            'client_id': self.client_id,
            'client_secret': RAW_SECRET,
        }), content_type=FORM)

    def bearer(self, access_token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer {}'.format(access_token))
        return client

    def change(self, client, current=OLD_PASSWORD, new=NEW_PASSWORD):
        return client.post(
            CHANGE, {'current_password': current, 'new_password': new}, format='json',
        )

    # -- behaviour --------------------------------------------------------

    def test_changes_password_and_new_one_works_at_auth_token(self):
        tokens = self.login().json()
        response = self.change(self.bearer(tokens['access_token']))
        self.assertEqual(200, response.status_code, response.content)

        # 400 `invalid_grant`, not 401: that is what the OAuth2 password
        # grant answers for a bad credential (RFC 6749 section 5.2).
        self.assertEqual(400, self.login().status_code)
        self.assertEqual(200, self.login(password=NEW_PASSWORD).status_code)

    def test_every_token_is_revoked_including_the_callers_own(self):
        first = self.login().json()
        second = self.login().json()

        self.assertEqual(200, self.change(self.bearer(first['access_token'])).status_code)

        for tokens in (first, second):
            self.assertEqual(401, self.bearer(tokens['access_token']).get('/api/me').status_code)
        self.assertEqual(0, get_access_token_model().objects.filter(user=self.user).count())
        self.assertEqual(0, get_refresh_token_model().objects.filter(user=self.user).count())

    def test_revoked_refresh_token_cannot_mint_a_new_pair(self):
        """`RefreshToken.revoke()` is a SOFT revoke that the refresh grant
        still honours inside `REFRESH_TOKEN_GRACE_PERIOD_SECONDS`. Deleting is
        what actually closes the door -- this test is the reason
        `selectors/auth_tokens.py` deletes rather than revokes."""
        tokens = self.login().json()
        self.change(self.bearer(tokens['access_token']))

        response = self.client.post(TOKEN_URL, data=urlencode({
            'grant_type': 'refresh_token',
            'refresh_token': tokens['refresh_token'],
            'client_id': self.client_id,
            'client_secret': RAW_SECRET,
        }), content_type=FORM)
        self.assertEqual(400, response.status_code, response.content)

    def test_wrong_current_password_changes_nothing(self):
        client = self.bearer(self.login().json()['access_token'])
        response = self.change(client, current='SaiBetHet!2026')
        self.assertEqual(400, response.status_code)
        self.assertIn('current_password', response.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))

    def test_weak_new_password_changes_nothing(self):
        client = self.bearer(self.login().json()['access_token'])
        response = self.change(client, new='123456')
        self.assertEqual(400, response.status_code)
        self.assertIn('new_password', response.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD_PASSWORD))

    def test_new_password_equal_to_current_is_rejected(self):
        client = self.bearer(self.login().json()['access_token'])
        response = self.change(client, new=OLD_PASSWORD)
        self.assertEqual(400, response.status_code)
        self.assertIn('new_password', response.json())

    def test_unauthenticated_is_401(self):
        self.assertEqual(401, APIClient().post(
            CHANGE, {'current_password': OLD_PASSWORD, 'new_password': NEW_PASSWORD},
            format='json').status_code)

    def test_unusable_password_account_is_pointed_at_the_reset_flow(self):
        client = self.bearer(self.login().json()['access_token'])
        self.user.set_unusable_password()
        self.user.save()
        response = self.change(client)
        self.assertEqual(400, response.status_code)
        self.assertIn('current_password', response.json())


class RegisterThenLoginTests(TestCase):
    """The whole product flow: register -> log in -> read `me`.

    This is the test that proves registration produces an account the existing,
    deliberately untouched `/auth/token` password grant accepts. If only one
    test in this feature survives, it should be this one.
    """

    @classmethod
    def setUpTestData(cls):
        staff = User.objects.create_user(username='app-owner', password='x')
        app = Application.objects.create(
            name='test-client',
            user=staff,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_PASSWORD,
            client_secret=RAW_SECRET,
        )
        cls.client_id = app.client_id

    def setUp(self):
        cache.clear()
        mail.outbox = []

    def token_for(self, password):
        return self.client.post(TOKEN_URL, data=urlencode({
            'grant_type': 'password',
            'username': EMAIL,
            'password': password,
            'client_id': self.client_id,
            'client_secret': RAW_SECRET,
        }), content_type=FORM)

    def test_register_then_login_then_read_me(self):
        registered = APIClient().post('/api/auth/register', {
            'email': EMAIL, 'password': OLD_PASSWORD,
            'first_name': 'An', 'last_name': 'Nguyễn',
        }, format='json')
        self.assertEqual(201, registered.status_code, registered.content)

        token_response = self.token_for(OLD_PASSWORD)
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

        self.assertEqual(400, self.token_for(OLD_PASSWORD).status_code)
        self.assertEqual(200, self.token_for(NEW_PASSWORD).status_code)
