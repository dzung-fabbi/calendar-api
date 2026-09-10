"""`POST /api/auth/login`, `/api/auth/refresh`, `/api/auth/logout` -- the only login path.

What this file guards: 401 (never 403 -- the DRF downgrade trap) is the answer
to every bad credential and every bad token; wrong password, unknown user and a
disabled account are byte-identical; a refresh token is single-use; a password
change kills a live access token without any token table being consulted.

Asserts against `/api/me`, an `apis/` endpoint -- `giapha/` has its own
anonymous-401 guard in `giapha/tests/test_permissions.py`.
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apis.models import RefreshToken
from apis.selectors.auth_tokens import set_password_and_revoke_tokens
from apis.services.jwt_tokens import encode_access_token

LOGIN = '/api/auth/login'
REFRESH = '/api/auth/refresh'
LOGOUT = '/api/auth/logout'
ME = '/api/me'
PUBLIC = '/api/get-config'  # no permission class, works on empty tables
FORM = 'application/x-www-form-urlencoded'

USERNAME = 'login.test@example.com'
PASSWORD = 'MatKhauManh!2026'
PAYLOAD_KEYS = {'access_token', 'refresh_token', 'token_type', 'expires_in'}


class AuthLoginAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username=USERNAME, email=USERNAME, password=PASSWORD)

    def setUp(self):
        # `auth-login` is 20/hour per IP and the suite shares one process cache.
        cache.clear()

    # -- helpers -----------------------------------------------------------

    def _login(self, username=USERNAME, password=PASSWORD):
        return APIClient().post(LOGIN, {'username': username, 'password': password}, format='json')

    def _tokens(self):
        response = self._login()
        self.assertEqual(200, response.status_code, response.content)
        return response.json()

    def _bearer(self, access_token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Bearer {}'.format(access_token))
        return client

    def _refresh(self, raw):
        return APIClient().post(REFRESH, {'refresh_token': raw}, format='json')

    def _logout(self, raw):
        return APIClient().post(LOGOUT, {'refresh_token': raw}, format='json')

    # -- issuance ----------------------------------------------------------

    def test_login_form_encoded_body(self):
        response = self.client.post(
            LOGIN, data=urlencode({'username': USERNAME, 'password': PASSWORD}), content_type=FORM)
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(PAYLOAD_KEYS, set(body))
        self.assertEqual('Bearer', body['token_type'])
        self.assertEqual(1, RefreshToken.objects.filter(user=self.user).count())

    def test_login_json_body(self):
        self.assertEqual(PAYLOAD_KEYS, set(self._tokens()))

    def test_login_missing_password_is_400_field_error(self):
        response = APIClient().post(LOGIN, {'username': USERNAME}, format='json')
        self.assertEqual(400, response.status_code)
        self.assertIn('password', response.json())

    def test_login_wrong_password_is_401_with_generic_detail(self):
        response = self._login(password='SaiBetHet!2026')
        self.assertEqual(401, response.status_code, response.content)
        self.assertEqual({'detail'}, set(response.json()))
        self.assertNotIn(b'access_token', response.content)

    def test_unknown_user_and_inactive_user_are_indistinguishable_from_wrong_password(self):
        User.objects.create_user(username='khoa@example.com', password=PASSWORD, is_active=False)
        wrong = self._login(password='SaiBetHet!2026')
        unknown = self._login(username='khong.ton.tai@example.com')
        inactive = self._login(username='khoa@example.com')
        for response in (unknown, inactive):
            self.assertEqual(401, response.status_code)
            self.assertEqual(wrong.content, response.content)

    def test_login_is_throttled_per_ip(self):
        for _ in range(20):
            self.assertEqual(401, self._login(password='sai').status_code)
        self.assertEqual(429, self._login().status_code)

    # -- the token authenticates ------------------------------------------

    def test_access_token_authenticates_me(self):
        response = self._bearer(self._tokens()['access_token']).get(ME)
        self.assertEqual(200, response.status_code, response.content)
        self.assertEqual(USERNAME, response.json()['data']['email'])

    def test_anonymous_is_401_not_403(self):
        self.assertEqual(401, APIClient().get(ME).status_code)

    def test_garbage_and_tampered_bearer_are_401(self):
        token = self._tokens()['access_token']
        tampered = token[:-1] + ('A' if token[-1] != 'A' else 'B')
        for value in ('not-a-jwt', tampered, token + ' extra'):
            with self.subTest(value=value[:12]):
                self.assertEqual(401, self._bearer(value).get(ME).status_code)

    def test_expired_access_token_is_401(self):
        yesterday = datetime.now(tz=timezone.utc) - timedelta(days=1)
        token, _ = encode_access_token(self.user.pk, self.user.password, now=yesterday)
        self.assertEqual(401, self._bearer(token).get(ME).status_code)

    def test_public_endpoint_needs_no_header(self):
        """The authenticator must return None, not raise, on a missing header."""
        self.assertEqual(200, APIClient().get(PUBLIC).status_code)

    def test_non_bearer_scheme_is_anonymous_not_an_error(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION='Token abc')
        self.assertEqual(200, client.get(PUBLIC).status_code)
        self.assertEqual(401, client.get(ME).status_code)

    # -- refresh ----------------------------------------------------------

    def test_refresh_rotates_and_the_old_token_is_single_use(self):
        first = self._tokens()
        rotated = self._refresh(first['refresh_token'])
        self.assertEqual(200, rotated.status_code, rotated.content)
        second = rotated.json()
        self.assertEqual(PAYLOAD_KEYS, set(second))
        self.assertNotEqual(first['refresh_token'], second['refresh_token'])
        self.assertEqual(401, self._refresh(first['refresh_token']).status_code)
        self.assertEqual(200, self._bearer(second['access_token']).get(ME).status_code)
        self.assertEqual(1, RefreshToken.objects.filter(user=self.user).count())

    def test_refresh_unknown_token_is_401(self):
        self.assertEqual(401, self._refresh('khong-ton-tai').status_code)

    def test_refresh_for_deactivated_user_is_401(self):
        raw = self._tokens()['refresh_token']
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(401, self._refresh(raw).status_code)

    def test_refresh_with_expired_row_is_401(self):
        raw = self._tokens()['refresh_token']
        RefreshToken.objects.filter(user=self.user).update(
            expires_at=datetime.now(tz=timezone.utc) - timedelta(seconds=1))
        self.assertEqual(401, self._refresh(raw).status_code)

    def test_refresh_after_a_plain_set_password_is_401(self):
        """Admin / shell / `changepassword` rewrite the hash without touching
        this table; the stored fingerprint is what still closes the door."""
        raw = self._tokens()['refresh_token']
        user = User.objects.get(pk=self.user.pk)
        user.set_password('DoiBangAdmin!2026')
        user.save()
        self.assertEqual(401, self._refresh(raw).status_code)
        self.assertEqual(0, RefreshToken.objects.filter(user=self.user).count())

    # -- logout -----------------------------------------------------------

    def test_logout_deletes_the_refresh_token(self):
        raw = self._tokens()['refresh_token']
        response = self._logout(raw)
        self.assertEqual(204, response.status_code)
        self.assertEqual(b'', response.content)
        self.assertEqual(401, self._refresh(raw).status_code)

    def test_logout_unknown_token_is_204(self):
        self.assertEqual(204, self._logout('khong-ton-tai').status_code)

    # -- password change --------------------------------------------------

    def test_password_change_kills_live_access_token_and_refresh_rows(self):
        tokens = self._tokens()
        client = self._bearer(tokens['access_token'])
        self.assertEqual(200, client.get(ME).status_code)

        # A fresh instance: Django 3.1 shares setUpTestData objects across tests.
        set_password_and_revoke_tokens(User.objects.get(pk=self.user.pk), 'MatKhauMoi!2026')

        self.assertEqual(401, client.get(ME).status_code)
        self.assertEqual(401, self._refresh(tokens['refresh_token']).status_code)
        self.assertEqual(0, RefreshToken.objects.filter(user=self.user).count())
