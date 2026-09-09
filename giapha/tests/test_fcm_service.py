"""Unit tests for `giapha.services.fcm` and `giapha.services.fcm_auth`. No DB,
and -- critically -- NO NETWORK: `requests.post` and the OAuth mint step are
both patched in every test, so the suite can never reach fcm.googleapis.com.

`fcm_auth._mint_token` is the seam for the credentials layer (patching it also
means these tests pass whether or not `google-auth` is installed in the image).
"""

import json
import os
import tempfile
from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings

from giapha.services import fcm, fcm_auth

SERVICE_ACCOUNT = {'project_id': 'giapha-test', 'client_email': 'x@y.iam.gserviceaccount.com'}


class FakeResponse(object):
    """Just enough of `requests.Response` for `_send_one`/`_classify`."""

    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError('no json')
        return self._payload


def fcm_error(status, error_code=None):
    error = {'code': 404, 'message': 'boom', 'status': status}
    if error_code:
        error['details'] = [{
            '@type': 'type.googleapis.com/google.firebase.fcm.v1.FcmError',
            'errorCode': error_code,
        }]
    return {'error': error}


@override_settings(FIREBASE_CREDENTIALS_PATH='', FIREBASE_CREDENTIALS_JSON='')
class FcmServiceTestCase(SimpleTestCase):
    """Clears the module-level token cache and both credential env vars so
    tests never leak state into each other or read a developer's real
    service account.

    THE SETTINGS LAYER HAS TO BE BLANKED HERE, not just the env. Every test
    below uses `os.environ` as its seam, but `fcm_auth._setting()` reads
    `settings.FIREBASE_*` FIRST and only falls back to the env when that is
    empty -- and `settings.py` populates both from the environment at import
    time. So in a process that has real credentials exported (the production
    app container, where `manage.py test` genuinely runs) `patch.dict` was
    silently ineffective: the "absent credentials" tests loaded the real
    service account and reached fcm.googleapis.com for real, against the
    module docstring's NO NETWORK promise. Blanking the settings restores
    the env as the only seam, on any host.
    """

    def setUp(self):
        fcm_auth._token_cache.update({'key': None, 'value': None, 'expires_at': 0.0})
        patcher = mock.patch.dict(
            os.environ, {'FIREBASE_CREDENTIALS_JSON': json.dumps(SERVICE_ACCOUNT)},
        )
        patcher.start()
        os.environ.pop('FIREBASE_CREDENTIALS_PATH', None)
        self.addCleanup(patcher.stop)
        self.addCleanup(
            fcm_auth._token_cache.update, {'key': None, 'value': None, 'expires_at': 0.0},
        )

    def without_credentials(self):
        return mock.patch.dict(os.environ, {}, clear=True)


class MissingCredentialsTests(FcmServiceTestCase):
    def test_no_env_returns_empty_result_and_never_raises(self):
        with self.without_credentials():
            with mock.patch('giapha.services.fcm.requests.post') as post:
                result = fcm.send_multicast(['tok-a'], 'T', 'B', {'type': 'gio'})
        self.assertEqual({}, result)
        post.assert_not_called()

    def test_malformed_credentials_json_is_treated_as_absent(self):
        with mock.patch.dict(os.environ, {'FIREBASE_CREDENTIALS_JSON': 'not-json'}):
            with mock.patch('giapha.services.fcm.requests.post') as post:
                result = fcm.send_multicast(['tok-a'], 'T', 'B')
        self.assertEqual({}, result)
        post.assert_not_called()

    def test_unreadable_credentials_path_is_transient_not_absent(self):
        """A path that is set but cannot be read is WEATHER, not config.

        The file is expected to exist -- someone configured it -- so it was
        most likely rotated out from under a running job. Returning `{}` here
        would tell the command "Firebase is off" and make it abandon every
        remaining recipient in the run, losing the day's reminders to a
        routine credential rotation. `ERROR_NETWORK` marks each recipient
        retriable instead, which the `status='sent'` dedupe then honours.
        """
        env = {'FIREBASE_CREDENTIALS_PATH': '/nowhere/service-account.json'}
        with mock.patch.dict(os.environ, env, clear=True):
            result = fcm.send_multicast(['tok-a', 'tok-b'], 'T', 'B')
        self.assertEqual(
            {'tok-a': fcm.ERROR_NETWORK, 'tok-b': fcm.ERROR_NETWORK}, result,
        )

    def test_malformed_credentials_file_is_treated_as_absent(self):
        """Malformed contents ARE config -- retrying cannot fix bad JSON."""
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False)
        handle.write('not-json')
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        with mock.patch.dict(
            os.environ, {'FIREBASE_CREDENTIALS_PATH': handle.name}, clear=True,
        ):
            result = fcm.send_multicast(['tok-a'], 'T', 'B')
        self.assertEqual({}, result)

    def test_service_account_without_project_id_is_disabled(self):
        with mock.patch.dict(os.environ, {'FIREBASE_CREDENTIALS_JSON': '{}'}):
            result = fcm.send_multicast(['tok-a'], 'T', 'B')
        self.assertEqual({}, result)

    def test_no_tokens_short_circuits(self):
        with mock.patch('giapha.services.fcm_auth._mint_token') as mint:
            self.assertEqual({}, fcm.send_multicast([], 'T', 'B'))
        mint.assert_not_called()

    def test_unmintable_token_returns_empty_rather_than_raising(self):
        with mock.patch('giapha.services.fcm_auth._mint_token', return_value=None):
            with mock.patch('giapha.services.fcm.requests.post') as post:
                result = fcm.send_multicast(['tok-a'], 'T', 'B')
        self.assertEqual({}, result)
        post.assert_not_called()


class TransientAuthTests(FcmServiceTestCase):
    """`{}` means "not configured" and nothing else -- a blip minting the
    OAuth token is weather, and the caller must be able to tell them apart.
    """

    def test_a_transient_mint_failure_is_reported_per_token_not_as_empty(self):
        with mock.patch(
            'giapha.services.fcm_auth._mint_token',
            side_effect=fcm_auth.FcmTransientError('dns'),
        ):
            with mock.patch('giapha.services.fcm.requests.post') as post:
                result = fcm.send_multicast(['tok-a', 'tok-b'], 'T', 'B')

        self.assertEqual({'tok-a': fcm.ERROR_NETWORK, 'tok-b': fcm.ERROR_NETWORK}, result)
        self.assertNotEqual({}, result, 'a transient failure must not read as "unconfigured"')
        post.assert_not_called()

    def test_a_transient_result_never_deactivates_a_token(self):
        self.assertNotIn(fcm.ERROR_NETWORK, fcm.DEAD_TOKEN_RESULTS)

    def test_the_cache_layer_propagates_the_transient_error(self):
        """`access_token` must not swallow it into `None` -- that is exactly
        the collapse that made the caller stop the whole run.
        """
        with mock.patch(
            'giapha.services.fcm_auth._mint_token',
            side_effect=fcm_auth.FcmTransientError('timeout'),
        ):
            with self.assertRaises(fcm_auth.FcmTransientError):
                fcm_auth.access_token(SERVICE_ACCOUNT)


class SendMulticastTests(FcmServiceTestCase):
    def send(self, responses, tokens=('tok-a', 'tok-b', 'tok-c')):
        """`responses`: what `requests.post` returns per call, in order --
        a `FakeResponse` or an exception instance to raise.
        """
        with mock.patch('giapha.services.fcm_auth._mint_token', return_value='bearer-1'):
            with mock.patch('giapha.services.fcm.requests.post', side_effect=responses) as post:
                result = fcm.send_multicast(list(tokens), 'Sắp đến ngày giỗ', 'body', {'id': 7})
        return result, post

    def test_all_tokens_succeed(self):
        result, post = self.send([FakeResponse(200, {'name': 'x'})] * 3)
        self.assertEqual({'tok-a': 'ok', 'tok-b': 'ok', 'tok-c': 'ok'}, result)
        self.assertEqual(3, post.call_count)

    def test_one_failing_token_does_not_abort_the_others(self):
        result, post = self.send([
            FakeResponse(200, {'name': 'x'}),
            FakeResponse(503, fcm_error('UNAVAILABLE')),
            FakeResponse(200, {'name': 'x'}),
        ])
        self.assertEqual('ok', result['tok-a'])
        self.assertEqual('ok', result['tok-c'])
        self.assertEqual('HTTP 503 UNAVAILABLE', result['tok-b'])
        self.assertEqual(3, post.call_count)

    def test_network_exception_is_captured_per_token(self):
        result, post = self.send([
            requests.ConnectionError('down'),
            FakeResponse(200, {'name': 'x'}),
            FakeResponse(200, {'name': 'x'}),
        ])
        self.assertEqual(fcm.ERROR_NETWORK, result['tok-a'])
        self.assertEqual('ok', result['tok-b'])
        self.assertEqual(3, post.call_count)

    def test_unregistered_is_surfaced_distinctly(self):
        result, _ = self.send(
            [FakeResponse(404, fcm_error('NOT_FOUND', 'UNREGISTERED'))], tokens=('tok-a',),
        )
        self.assertEqual(fcm.ERROR_UNREGISTERED, result['tok-a'])
        self.assertIn(result['tok-a'], fcm.DEAD_TOKEN_RESULTS)

    def test_invalid_argument_is_surfaced_distinctly(self):
        result, _ = self.send(
            [FakeResponse(400, fcm_error('INVALID_ARGUMENT'))], tokens=('tok-a',),
        )
        self.assertEqual(fcm.ERROR_INVALID_ARGUMENT, result['tok-a'])
        self.assertIn(result['tok-a'], fcm.DEAD_TOKEN_RESULTS)

    def test_transient_failure_is_not_a_dead_token(self):
        result, _ = self.send([FakeResponse(500, None)], tokens=('tok-a',))
        self.assertNotIn(result['tok-a'], fcm.DEAD_TOKEN_RESULTS)
        self.assertEqual('HTTP 500', result['tok-a'])

    def test_payload_carries_token_notification_and_string_data(self):
        _, post = self.send([FakeResponse(200, {'name': 'x'})], tokens=('tok-a',))
        message = post.call_args[1]['json']['message']
        self.assertEqual('tok-a', message['token'])
        self.assertEqual('Sắp đến ngày giỗ', message['notification']['title'])
        self.assertEqual({'id': '7'}, message['data'])

    def test_authorization_header_uses_the_bearer_token(self):
        _, post = self.send([FakeResponse(200, {'name': 'x'})], tokens=('tok-a',))
        self.assertEqual('Bearer bearer-1', post.call_args[1]['headers']['Authorization'])


class AccessTokenCacheTests(FcmServiceTestCase):
    def test_token_is_minted_once_across_two_sends(self):
        ok = FakeResponse(200, {'name': 'x'})
        with mock.patch('giapha.services.fcm_auth._mint_token', return_value='bearer-1') as mint:
            with mock.patch('giapha.services.fcm.requests.post', return_value=ok):
                fcm.send_multicast(['tok-a'], 'T', 'B')
                fcm.send_multicast(['tok-b'], 'T', 'B')
        self.assertEqual(1, mint.call_count)

    def test_expired_cache_mints_again(self):
        ok = FakeResponse(200, {'name': 'x'})
        with mock.patch('giapha.services.fcm_auth._mint_token', return_value='bearer-1') as mint:
            with mock.patch('giapha.services.fcm.requests.post', return_value=ok):
                fcm.send_multicast(['tok-a'], 'T', 'B')
                fcm_auth._token_cache['expires_at'] = 0.0  # simulate TTL elapsing
                fcm.send_multicast(['tok-b'], 'T', 'B')
        self.assertEqual(2, mint.call_count)

    def test_a_different_service_account_is_not_served_the_cached_token(self):
        """The cache is keyed on the service account: after a rotation (or
        with two projects) an unkeyed cache would hand out a bearer token for
        the wrong project for the rest of its TTL.
        """
        ok = FakeResponse(200, {'name': 'x'})
        other = {'project_id': 'other', 'client_email': 'z@y.iam.gserviceaccount.com'}
        with mock.patch(
            'giapha.services.fcm_auth._mint_token', side_effect=['bearer-1', 'bearer-2'],
        ) as mint:
            with mock.patch('giapha.services.fcm.requests.post', return_value=ok) as post:
                fcm.send_multicast(['tok-a'], 'T', 'B')
                with mock.patch.dict(
                    os.environ, {'FIREBASE_CREDENTIALS_JSON': json.dumps(other)},
                ):
                    fcm.send_multicast(['tok-b'], 'T', 'B')

        self.assertEqual(2, mint.call_count)
        self.assertEqual(
            'Bearer bearer-2', post.call_args[1]['headers']['Authorization'],
        )

    def test_failed_mint_is_not_cached(self):
        with mock.patch('giapha.services.fcm_auth._mint_token', return_value=None) as mint:
            fcm.send_multicast(['tok-a'], 'T', 'B')
            fcm.send_multicast(['tok-b'], 'T', 'B')
        self.assertEqual(2, mint.call_count)


class RedactionTests(SimpleTestCase):
    def test_full_device_token_is_never_rendered(self):
        device_token = 'f' * 152
        rendered = fcm._redact(device_token)
        self.assertNotIn(device_token, rendered)
        self.assertLess(len(rendered), 30)
