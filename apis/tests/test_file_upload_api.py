"""API-level tests for the generic presigned S3/R2 file endpoints.

`boto3` is mocked completely -- `MockedBotoMixin` patches
`apis.services.storage.boto3.client` and calls `storage.reset_client_cache()`
so each test gets its own fresh `Mock` regardless of the config tuple staying
the same across tests in a class. NOTHING here touches the network.

`cache.clear()` in `setUp` is load-bearing, not hygiene: both endpoints are
unauthenticated and `ScopedRateThrottle` buckets by IP, every test client here
shares one `REMOTE_ADDR`, and `LocMemCache` is process-wide -- so without the
reset an earlier class's 20 requests would spend a later class's budget and
turn unrelated assertions into 429s. Only `FileUploadThrottleTests` wants the
throttle to fire.
"""

import uuid
from unittest import mock

from botocore.exceptions import ClientError
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apis.services import storage
from djangopj.settings import REST_FRAMEWORK

S3_TEST_SETTINGS = dict(
    S3_ENDPOINT_URL='', S3_BUCKET='test-bucket', S3_ACCESS_KEY_ID='test-key',
    S3_SECRET_ACCESS_KEY='test-secret', S3_REGION='auto',
)

SIGNED_URL = 'https://test-bucket.example/signed'


def upload_url_endpoint():
    return reverse('file-upload-url')


def confirm_endpoint():
    return reverse('file-confirm')


def a_key(extension='jpg'):
    """A key shaped exactly like the one the server mints."""
    return 'uploads/{}.{}'.format(uuid.uuid4().hex, extension)


class MockedBotoMixin:
    def setUp(self):
        super().setUp()
        cache.clear()
        storage.reset_client_cache()
        patcher = mock.patch('apis.services.storage.boto3.client')
        self.mock_boto_client_factory = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_client = mock.Mock()
        self.mock_boto_client_factory.return_value = self.mock_client
        self.mock_client.generate_presigned_url.return_value = SIGNED_URL
        self.mock_client.head_object.return_value = {
            'ContentLength': 1000, 'ContentType': 'image/jpeg',
        }


@override_settings(**S3_TEST_SETTINGS)
class FileUploadUrlTests(MockedBotoMixin, TestCase):
    def post(self, body):
        return APIClient().post(upload_url_endpoint(), body, format='json')

    def test_anonymous_caller_gets_a_presigned_upload_url(self):
        """AllowAny: no token, no 401. This is the accepted risk documented in
        `apis/views/file_upload.py`."""
        response = self.post({'content_type': 'image/jpeg', 'size': 1000})
        self.assertEqual(200, response.status_code)
        data = response.json()['data']
        self.assertEqual(SIGNED_URL, data['upload_url'])
        self.assertEqual(300, data['expires_in'])

    def test_minted_key_has_the_uploads_prefix_and_a_bare_uuid_name(self):
        response = self.post({'content_type': 'image/png', 'size': 10})
        key = response.json()['data']['key']
        self.assertRegex(key, r'^uploads/[0-9a-f]{32}\.png$')

    def test_extension_follows_the_declared_content_type(self):
        for content_type, extension in (
            ('image/jpeg', 'jpg'), ('image/png', 'png'), ('image/webp', 'webp'),
        ):
            with self.subTest(content_type=content_type):
                key = self.post({'content_type': content_type, 'size': 10}).json()['data']['key']
                self.assertTrue(key.endswith('.' + extension), key)

    def test_content_type_is_passed_to_the_presigner(self):
        """The presigned PUT pins `ContentType`; a client uploading with a
        different header gets a signature mismatch from S3 itself."""
        self.post({'content_type': 'image/webp', 'size': 10})
        params = self.mock_client.generate_presigned_url.call_args.kwargs['Params']
        self.assertEqual('image/webp', params['ContentType'])
        self.assertEqual('test-bucket', params['Bucket'])

    def test_disallowed_content_type_is_rejected(self):
        for content_type in ('application/pdf', 'text/html', 'image/svg+xml', 'image/gif'):
            with self.subTest(content_type=content_type):
                response = self.post({'content_type': content_type, 'size': 1000})
                self.assertEqual(400, response.status_code)

    def test_oversized_declared_size_is_rejected(self):
        response = self.post({'content_type': 'image/jpeg', 'size': 5 * 1024 * 1024 + 1})
        self.assertEqual(400, response.status_code)

    def test_zero_size_is_rejected(self):
        self.assertEqual(400, self.post({'content_type': 'image/jpeg', 'size': 0}).status_code)

    def test_missing_fields_are_rejected(self):
        for body in ({}, {'size': 10}, {'content_type': 'image/jpeg'}):
            with self.subTest(body=body):
                self.assertEqual(400, self.post(body).status_code)

    def test_nothing_is_written_to_storage_at_mint_time(self):
        self.post({'content_type': 'image/jpeg', 'size': 10})
        self.mock_client.head_object.assert_not_called()
        self.mock_client.put_object.assert_not_called()


@override_settings(**S3_TEST_SETTINGS)
class FileConfirmTests(MockedBotoMixin, TestCase):
    def confirm(self, key):
        return APIClient().post(confirm_endpoint(), {'key': key}, format='json')

    def test_confirm_returns_a_presigned_get_url(self):
        key = a_key()
        response = self.confirm(key)
        self.assertEqual(200, response.status_code)
        data = response.json()['data']
        self.assertEqual(key, data['key'])
        self.assertEqual(SIGNED_URL, data['url'])
        self.assertEqual(3600, data['expires_in'])

    def test_confirm_heads_the_object_it_was_given(self):
        key = a_key()
        self.confirm(key)
        self.mock_client.head_object.assert_called_once_with(Bucket='test-bucket', Key=key)

    def test_missing_object_is_rejected(self):
        """S3 answers 404/NoSuchKey/NotFound depending on provider; all three
        mean the client named a key nothing was ever uploaded to -> 400."""
        for code in ('404', 'NoSuchKey', 'NotFound'):
            with self.subTest(code=code):
                self.mock_client.head_object.side_effect = ClientError(
                    {'Error': {'Code': code}}, 'HeadObject',
                )
                self.assertEqual(400, self.confirm(a_key()).status_code)

    def test_access_denied_is_treated_as_not_found(self):
        """A credential without `s3:ListBucket` answers 403 for a missing key
        instead of 404 -- the default for an object-scoped R2 token. Without
        this mapping that normal setup would 500 on every unknown key."""
        self.mock_client.head_object.side_effect = ClientError(
            {'Error': {'Code': 'AccessDenied'}}, 'HeadObject',
        )
        self.assertEqual(400, self.confirm(a_key()).status_code)

    def test_other_client_errors_are_not_swallowed(self):
        """A genuine fault (throttling, outage, bad credentials) must NOT be
        reported to the caller as "your key is wrong"."""
        self.mock_client.head_object.side_effect = ClientError(
            {'Error': {'Code': 'InternalError'}}, 'HeadObject',
        )
        with self.assertRaises(ClientError):
            self.confirm(a_key())

    def test_oversized_object_is_rejected(self):
        """The 5MB cap is enforced HERE, not at mint time -- a client that
        ignored its own declared `size` is caught by the real ContentLength."""
        self.mock_client.head_object.return_value = {
            'ContentLength': 5 * 1024 * 1024 + 1, 'ContentType': 'image/jpeg',
        }
        self.assertEqual(400, self.confirm(a_key()).status_code)

    def test_object_at_exactly_the_cap_is_accepted(self):
        self.mock_client.head_object.return_value = {
            'ContentLength': 5 * 1024 * 1024, 'ContentType': 'image/jpeg',
        }
        self.assertEqual(200, self.confirm(a_key()).status_code)

    def test_real_content_type_outside_the_allowlist_is_rejected(self):
        """The declared type at mint time is not trusted: what counts is what
        the object in the bucket actually is."""
        self.mock_client.head_object.return_value = {
            'ContentLength': 100, 'ContentType': 'text/html',
        }
        self.assertEqual(400, self.confirm(a_key()).status_code)

    def test_object_with_no_content_type_is_rejected(self):
        self.mock_client.head_object.return_value = {'ContentLength': 100}
        self.assertEqual(400, self.confirm(a_key()).status_code)

    def test_key_regex_rejects_a_trailing_newline(self):
        """Asserted against `_KEY_RE` DIRECTLY, not through the endpoint, and
        that is the whole point.

        A trailing newline cannot be driven through `confirm` at all: DRF's
        `CharField.trim_whitespace` defaults to True and strips it, so the view
        only ever sees the clean key (`test_trailing_whitespace_is_trimmed...`
        below pins that). Which means the endpoint can NEVER catch the anchor
        regressing from `\\Z` back to `$` -- and Python's `$` does match
        immediately before one trailing newline. Without this unit-level
        assertion the hole reopens silently the day `trim_whitespace=False`
        looks like a tightening.
        """
        from apis.views.file_upload import _KEY_RE
        key = 'uploads/{}.jpg'.format(uuid.uuid4().hex)
        self.assertIsNotNone(_KEY_RE.match(key))
        self.assertIsNone(_KEY_RE.match(key + '\n'))
        self.assertIsNone(_KEY_RE.match(key + '\r\n'))

    def test_trailing_whitespace_is_trimmed_before_the_key_is_validated(self):
        """Documents the layer the test above depends on: the serializer
        normalises the key, so a client sending a stray newline gets a 200 on
        the trimmed key rather than a 400."""
        key = a_key()
        response = self.confirm(key + '\n')
        self.assertEqual(200, response.status_code)
        self.assertEqual(key, response.json()['data']['key'])

    def test_malformed_keys_are_rejected_without_touching_storage(self):
        """A prefix check would accept most of these; the minted-shape regex
        does not. None of them may reach `head_object`."""
        bad_keys = [
            'uploads/../../etc/passwd',
            'uploads/',
            'uploads/notauuid.jpg',
            'uploads/{}.exe'.format(uuid.uuid4().hex),
            'uploads/{}'.format(uuid.uuid4().hex),
            'uploads/{}.jpg\nx'.format(uuid.uuid4().hex),
            'uploads/sub/{}.jpg'.format(uuid.uuid4().hex),
            'giapha/1/2/{}.jpg'.format(uuid.uuid4().hex),
            '{}.jpg'.format(uuid.uuid4().hex),
            'uploads/{}.JPG'.format(uuid.uuid4().hex),
            'uploads/{}.jpg'.format(uuid.uuid4().hex.upper()),
        ]
        for key in bad_keys:
            with self.subTest(key=key):
                self.assertEqual(400, self.confirm(key).status_code)
        self.mock_client.head_object.assert_not_called()

    def test_missing_key_field_is_rejected(self):
        response = APIClient().post(confirm_endpoint(), {}, format='json')
        self.assertEqual(400, response.status_code)


class StorageUnconfiguredTests(MockedBotoMixin, TestCase):
    """Deliberately NO `@override_settings` -- the test settings leave every
    `S3_*` variable empty, which is the state every other `apis` test runs in.
    Both endpoints must answer 503 there, and the rest of the API must not
    care.
    """

    def test_upload_url_is_503(self):
        response = APIClient().post(
            upload_url_endpoint(), {'content_type': 'image/jpeg', 'size': 10}, format='json',
        )
        self.assertEqual(503, response.status_code)

    def test_confirm_is_503(self):
        response = APIClient().post(confirm_endpoint(), {'key': a_key()}, format='json')
        self.assertEqual(503, response.status_code)

    def test_503_comes_before_body_validation(self):
        """An unconfigured host answers 503 even for a request that would also
        have failed validation -- the operator fault is the useful answer."""
        response = APIClient().post(
            upload_url_endpoint(), {'content_type': 'application/pdf'}, format='json',
        )
        self.assertEqual(503, response.status_code)

    def test_another_endpoint_still_works_with_no_storage_configured(self):
        self.assertEqual(200, APIClient().get(reverse('get-config')).status_code)


@override_settings(**S3_TEST_SETTINGS)
class FileUploadThrottleTests(MockedBotoMixin, TestCase):
    """`ScopedRateThrottle.THROTTLE_RATES` is bound from `api_settings` at
    class-definition time (module import), so `override_settings` on
    `REST_FRAMEWORK` cannot change it for an already-imported throttle class --
    this exercises the real configured rate directly instead.
    """

    def limit(self):
        return int(REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['file-upload'].split('/')[0])

    def test_repeated_upload_url_requests_are_eventually_throttled(self):
        client = APIClient()
        body = {'content_type': 'image/jpeg', 'size': 10}
        limit = self.limit()
        statuses = [
            client.post(upload_url_endpoint(), body, format='json').status_code
            for _ in range(limit + 1)
        ]
        self.assertNotIn(429, statuses[:limit], 'requests within the configured rate must not be throttled')
        self.assertEqual(429, statuses[-1], 'the request past the configured rate must be throttled')

    def test_both_endpoints_share_one_bucket(self):
        """Same `throttle_scope`, so spending the budget on `upload-url` must
        also throttle `confirm` -- otherwise the cap is twice what it says."""
        client = APIClient()
        body = {'content_type': 'image/jpeg', 'size': 10}
        for _ in range(self.limit()):
            client.post(upload_url_endpoint(), body, format='json')
        response = client.post(confirm_endpoint(), {'key': a_key()}, format='json')
        self.assertEqual(429, response.status_code)

    def test_the_file_upload_scope_does_not_throttle_other_endpoints(self):
        client = APIClient()
        body = {'content_type': 'image/jpeg', 'size': 10}
        for _ in range(self.limit() + 1):
            client.post(upload_url_endpoint(), body, format='json')
        self.assertEqual(200, client.get(reverse('get-config')).status_code)
