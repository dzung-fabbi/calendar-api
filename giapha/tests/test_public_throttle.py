"""Throttle tests for `giapha-public` (phase-9 public gia phả surface).

Split out of `test_public_security.py` once that file crossed the
200-line ceiling.
"""

from django.core.cache import cache
from django.test import TestCase

from djangopj.settings import REST_FRAMEWORK
from giapha.tests.factories import build_clan_fixture
from giapha.tests.public_helpers import anon_client, enable_public_link, public_tree_url


class PublicThrottleTests(TestCase):
    """`ScopedRateThrottle.THROTTLE_RATES` binds from `api_settings` at
    class-definition (import) time, same caveat as
    `test_invites_and_join.JoinThrottleTests` -- this exercises the real
    configured rate rather than trying to `override_settings` it.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_public_throttle')
        cls.clan = cls.fixture['clan']
        cls.slug = enable_public_link(cls.clan)

    def setUp(self):
        cache.clear()

    def test_repeated_requests_are_eventually_throttled(self):
        limit = int(REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['giapha-public'].split('/')[0])
        client = anon_client()
        statuses = [client.get(public_tree_url(self.slug)).status_code for _ in range(limit + 1)]
        self.assertNotIn(429, statuses[:limit], 'requests within the configured rate must not be throttled')
        self.assertEqual(429, statuses[-1], 'the request past the configured rate must be throttled')


class ThrottleIdentBypassTests(TestCase):
    """Security fix (phase-9 review H3): with `NUM_PROXIES` unset, DRF's
    `BaseThrottle.get_ident` uses the RAW `X-Forwarded-For` header value as
    the throttle bucket key -- so a caller who sends a different value on
    every request picks a fresh, empty bucket every time and the rate limit
    never fires at all (proven during review: 70 requests with a rotating
    header, zero 429s). `djangopj.settings.REST_FRAMEWORK['NUM_PROXIES']`
    is now explicitly `0` by default (`DJANGO_NUM_PROXIES` env var, see
    `.env.example`), which makes DRF ignore `X-Forwarded-For` entirely and
    bucket by `REMOTE_ADDR` alone -- the header becomes inert for an
    edge-facing deployment (the only topology assumed safe by default).
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_public_throttle_xff')
        cls.clan = cls.fixture['clan']
        cls.slug = enable_public_link(cls.clan)

    def setUp(self):
        cache.clear()

    def test_rotating_x_forwarded_for_does_not_create_a_new_bucket(self):
        limit = int(REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['giapha-public'].split('/')[0])
        client = anon_client()
        statuses = [
            client.get(
                public_tree_url(self.slug),
                HTTP_X_FORWARDED_FOR='10.0.0.{}'.format(i),
            ).status_code
            for i in range(limit + 1)
        ]
        self.assertIn(
            429, statuses,
            'a rotating X-Forwarded-For header must not let the caller escape the shared REMOTE_ADDR bucket',
        )
        self.assertEqual(
            429, statuses[-1],
            'the request past the configured rate must be throttled exactly like the no-header case',
        )
