"""Regression guard for `/auth/token` and `/auth/revoke-token`.

Login is username/password only. `djangopj.auth_token_views` serves both URLs.
The contract that matters is that SHIPPED CLIENTS SEE NO CHANGE: same paths,
optional trailing slash, and -- the easy one to lose -- a JSON body works just as
well as a form-encoded one. django-oauth-toolkit's own views are form-only, so
`test_token_json_body` is what fails the moment someone swaps the shim out for
`oauth2_provider.views.TokenView`.
"""
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.test import TestCase
from oauth2_provider.models import Application

FORM_CONTENT_TYPE = 'application/x-www-form-urlencoded'

# `Application.client_secret` is hashed by `ClientSecretField.pre_save`, so the
# value read back off the instance is useless for authenticating. Keep the
# plaintext here -- this is the single easiest way to lose an hour in this file.
RAW_SECRET = 'test-client-secret'
RAW_PASSWORD = 'test-password-123'
USERNAME = 'tokentest'

TOKEN_URL = '/auth/token'
REVOKE_URL = '/auth/revoke-token'
CLANS_URL = '/api/gia-pha/clans'



class AuthTokenEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username=USERNAME, password=RAW_PASSWORD)
        app = Application.objects.create(
            name='test-client',
            user=cls.user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            authorization_grant_type=Application.GRANT_PASSWORD,
            client_secret=RAW_SECRET,
        )
        cls.client_id = app.client_id  # not hashed, safe to read back

    def _post_token(self, json_body=False, url=TOKEN_URL, **overrides):
        payload = {
            'grant_type': 'password',
            'username': USERNAME,
            'password': RAW_PASSWORD,
            'client_id': self.client_id,
            'client_secret': RAW_SECRET,
        }
        payload.update(overrides)
        if json_body:
            return self.client.post(url, data=payload, content_type='application/json')
        # Django's test client defaults to multipart, NOT urlencoded -- spelling
        # the content type out is the only way this actually covers what shipped
        # clients (and the `curl -d` in the deployment guide) send.
        return self.client.post(url, data=urlencode(payload), content_type=FORM_CONTENT_TYPE)

    def _issue_token(self):
        response = self._post_token()
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def _get_clans(self, token=None):
        if token is None:
            return self.client.get(CLANS_URL)
        return self.client.get(CLANS_URL, HTTP_AUTHORIZATION='Bearer ' + token)

    # --- issuance -------------------------------------------------------

    def test_token_form_encoded_body(self):
        body = self._issue_token()
        self.assertIn('access_token', body)
        self.assertIn('refresh_token', body)
        self.assertEqual(body['token_type'], 'Bearer')

    def test_token_json_body(self):
        """The regression this module exists for -- DOT's own view is form-only."""
        response = self._post_token(json_body=True)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn('access_token', response.json())

    def test_token_trailing_slash_is_optional(self):
        response = self._post_token(url=TOKEN_URL + '/')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn('access_token', response.json())

    def test_token_multipart_body(self):
        """Django's test-client default, and what some HTTP wrappers send."""
        response = self.client.post(TOKEN_URL, data={
            'grant_type': 'password',
            'username': USERNAME,
            'password': RAW_PASSWORD,
            'client_id': self.client_id,
            'client_secret': RAW_SECRET,
        })
        self.assertEqual(response.status_code, 200, response.content)

    def test_token_accepts_every_accept_header(self):
        """Narrowing `renderer_classes` to JSONRenderer would turn `text/html`
        into a 406 -- a silent, unrecoverable login failure for any client
        sending that header. This endpoint answered 200 before; keep it that way."""
        for accept in ('*/*', 'application/json', 'text/html',
                       'text/html,application/xhtml+xml,*/*;q=0.8'):
            with self.subTest(accept=accept):
                response = self.client.post(
                    TOKEN_URL,
                    data=urlencode({
                        'grant_type': 'password',
                        'username': USERNAME,
                        'password': RAW_PASSWORD,
                        'client_id': self.client_id,
                        'client_secret': RAW_SECRET,
                    }),
                    content_type=FORM_CONTENT_TYPE,
                    HTTP_ACCEPT=accept,
                )
                self.assertEqual(response.status_code, 200, response.content)

    def test_token_non_object_json_body_is_400_not_500(self):
        """A 6-byte unauthenticated request must not produce a 500 (and an error
        report carrying the request) -- the upstream package raised AttributeError
        on each of these."""
        for raw in ('[1,2,3]', '"hello"', 'null', '42'):
            with self.subTest(body=raw):
                response = self.client.post(
                    TOKEN_URL, data=raw, content_type='application/json')
                self.assertEqual(response.status_code, 400, response.content)

    def test_token_bad_client_secret_is_401_with_www_authenticate(self):
        response = self._post_token(client_secret='wrong-secret')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'invalid_client')
        # RFC 6749 section 5.2 requires the header on this response.
        self.assertIn('WWW-Authenticate', response)

    def test_token_wrong_password_is_invalid_grant(self):
        response = self._post_token(password='not-the-password')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'invalid_grant')

    def test_refresh_token_grant(self):
        refresh_token = self._issue_token()['refresh_token']
        response = self._post_token(
            json_body=True,
            grant_type='refresh_token',
            refresh_token=refresh_token,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn('access_token', response.json())

    # --- the token actually authenticates -------------------------------

    def test_issued_token_authenticates_a_real_endpoint(self):
        """Proves the trimmed DEFAULT_AUTHENTICATION_CLASSES still works."""
        token = self._issue_token()['access_token']
        self.assertEqual(self._get_clans().status_code, 401)
        response = self._get_clans(token)
        self.assertEqual(response.status_code, 200, response.content)

    # --- revocation -----------------------------------------------------

    def test_revoke_token_invalidates_it(self):
        token = self._issue_token()['access_token']
        response = self.client.post(
            REVOKE_URL,
            data={
                'client_id': self.client_id,
                'client_secret': RAW_SECRET,
                'token': token,
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204, response.content)
        # The body is empty on the wire no matter what we render: Django's test
        # client runs `conditional_content_removal`, which mirrors what real web
        # servers do to a 204 (RFC 7230 section 3.3.3). Upstream rendered
        # `data=''` and so do we -- the visible difference is the header:
        # `Response(status=204)` with no data sends no `Content-Type` at all.
        self.assertEqual(response.content, b'')
        self.assertIn('application/json', response['Content-Type'])
        self.assertEqual(self._get_clans(token).status_code, 401)

    def test_revoke_token_missing_client_secret_is_401_for_a_confidential_client(self):
        """`client_secret` is optional on the serializer so a PUBLIC client can log
        out. A confidential one that omits it has simply failed to authenticate, so
        the answer moves from a 400 field error to oauthlib's own 401."""
        response = self.client.post(
            REVOKE_URL,
            data={'client_id': self.client_id, 'token': 'whatever'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 401, response.content)
        self.assertEqual(response.json(), {'error': 'invalid_client'})

    def test_revoke_token_missing_token_keeps_field_error_shape(self):
        """The serializer still guards the two fields it requires."""
        response = self.client.post(
            REVOKE_URL,
            data={'client_id': self.client_id, 'client_secret': RAW_SECRET},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('token', response.json())


class PublicClientAuthTokenTests(TestCase):
    """The production application is a `public` client (see
    `_RevokeTokenSerializer`). A native app cannot hold a secret, so both
    endpoints must work with `client_id` alone -- this class is what fails if
    anyone makes `client_secret` mandatory again."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='publicclient', password=RAW_PASSWORD)
        app = Application.objects.create(
            name='test-public-client',
            user=cls.user,
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_PASSWORD,
        )
        cls.client_id = app.client_id

    def _issue_token(self):
        response = self.client.post(
            TOKEN_URL,
            data=urlencode({
                'grant_type': 'password',
                'username': 'publicclient',
                'password': RAW_PASSWORD,
                'client_id': self.client_id,
            }),
            content_type=FORM_CONTENT_TYPE,
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_token_without_client_secret(self):
        self.assertIn('access_token', self._issue_token())

    def test_token_with_blank_client_secret(self):
        """A client that keeps the field but empties it must not be pushed down
        the confidential branch -- `'' `is falsy, so client auth stays skipped."""
        response = self.client.post(
            TOKEN_URL,
            data=urlencode({
                'grant_type': 'password',
                'username': 'publicclient',
                'password': RAW_PASSWORD,
                'client_id': self.client_id,
                'client_secret': '',
            }),
            content_type=FORM_CONTENT_TYPE,
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_token_with_a_wrong_client_secret_is_still_rejected(self):
        """Sending SOME secret opts back into client authentication, which then
        fails. This is why an old build must drop the field, not blank-fill it."""
        response = self.client.post(
            TOKEN_URL,
            data=urlencode({
                'grant_type': 'password',
                'username': 'publicclient',
                'password': RAW_PASSWORD,
                'client_id': self.client_id,
                'client_secret': 'wrong-secret',
            }),
            content_type=FORM_CONTENT_TYPE,
        )
        self.assertEqual(response.status_code, 401, response.content)

    def test_revoke_token_without_client_secret(self):
        token = self._issue_token()['access_token']
        response = self.client.post(
            REVOKE_URL,
            data={'client_id': self.client_id, 'token': token},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(
            self.client.get(CLANS_URL, HTTP_AUTHORIZATION='Bearer ' + token).status_code,
            401,
        )
