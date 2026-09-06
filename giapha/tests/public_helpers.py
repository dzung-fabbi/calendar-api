"""Shared fixtures/helpers for the phase-9 public gia phả test suite.

Not itself a test file (no `test_` prefix, Django's test runner never
collects it) -- split out once `test_public_security.py` alone crossed the
200-line ceiling (`docs/code-standards.md` -> Files) and a second, third and
fourth test file needed the exact same URL builders / fixture helper /
throttle-safe base case.
"""

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.services.public_slug import generate_public_slug


def anon_client():
    return APIClient()


def public_tree_url(slug):
    return reverse('public-clan-tree', kwargs={'slug': slug})


def public_person_url(slug, person_id):
    return reverse('public-person-detail', kwargs={'slug': slug, 'person_id': person_id})


def enable_public_link(clan):
    """Direct model write -- equivalent to what `ClanPublicLinkAPIView.post`
    does, without the HTTP round trip (that endpoint has its own tests in
    `test_public_link_api.py`).
    """
    clan.public_slug = generate_public_slug()
    clan.visibility = 'public_link'
    clan.save(update_fields=['public_slug', 'visibility'])
    return clan.public_slug


def node_for(nodes, person_id):
    for node in nodes:
        if node['id'] == person_id:
            return node
    raise AssertionError('person {} not found in tree nodes'.format(person_id))


class PublicEndpointTestCase(TestCase):
    """Every test client below shares one `REMOTE_ADDR`, and
    `ScopedRateThrottle` buckets by IP for an unauthenticated caller -- so
    without clearing the cache between test classes, an earlier class's
    requests count against a later class's budget under the same
    process-wide `LocMemCache`. Only throttle-specific test classes
    actually want the throttle to fire; every other class here needs a
    clean bucket.
    """

    def setUp(self):
        super().setUp()
        cache.clear()
