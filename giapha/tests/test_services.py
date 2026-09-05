"""Unit tests for `giapha.services.invite_code`. No DB needed."""

import datetime as dt
from types import SimpleNamespace

from django.test import SimpleTestCase

from giapha.services.invite_code import ALPHABET, generate_code, is_exhausted, is_expired

NOW = dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc)


def _invite(expires_at=None, max_uses=0, used_count=0):
    return SimpleNamespace(expires_at=expires_at, max_uses=max_uses, used_count=used_count)


class GenerateCodeTests(SimpleTestCase):
    def test_default_length_is_eight(self):
        self.assertEqual(8, len(generate_code()))

    def test_respects_custom_length(self):
        self.assertEqual(12, len(generate_code(length=12)))

    def test_only_uses_the_unambiguous_alphabet(self):
        code = generate_code(length=200)
        self.assertTrue(set(code) <= set(ALPHABET))

    def test_excludes_ambiguous_characters(self):
        for banned in '0O1I':
            self.assertNotIn(banned, ALPHABET)

    def test_generates_different_codes(self):
        # Not a proof of randomness, just a sanity check against a constant.
        codes = {generate_code() for _ in range(20)}
        self.assertGreater(len(codes), 1)


class IsExpiredTests(SimpleTestCase):
    def test_no_expiry_never_expires(self):
        self.assertFalse(is_expired(_invite(expires_at=None), NOW))

    def test_future_expiry_is_not_expired(self):
        future = NOW + dt.timedelta(days=1)
        self.assertFalse(is_expired(_invite(expires_at=future), NOW))

    def test_past_expiry_is_expired(self):
        past = NOW - dt.timedelta(days=1)
        self.assertTrue(is_expired(_invite(expires_at=past), NOW))

    def test_expiry_exactly_now_is_expired(self):
        self.assertTrue(is_expired(_invite(expires_at=NOW), NOW))


class IsExhaustedTests(SimpleTestCase):
    def test_unlimited_uses_never_exhausted(self):
        self.assertFalse(is_exhausted(_invite(max_uses=0, used_count=1000)))

    def test_below_cap_is_not_exhausted(self):
        self.assertFalse(is_exhausted(_invite(max_uses=5, used_count=4)))

    def test_at_cap_is_exhausted(self):
        self.assertTrue(is_exhausted(_invite(max_uses=5, used_count=5)))

    def test_over_cap_is_exhausted(self):
        self.assertTrue(is_exhausted(_invite(max_uses=1, used_count=2)))
