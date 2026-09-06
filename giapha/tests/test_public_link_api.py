"""API-level tests for `POST`/`DELETE /clans/{clan_id}/public-link` -- the
owner-only toggle that mints/revokes the phase-9 public share slug.

Security-critical behaviour of the resulting no-auth surface (whitelist,
404 rules, throttle, canary) lives in `test_public_security.py`; this file
only covers the authenticated toggle itself.
"""

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.models import Clan
from giapha.tests.factories import build_clan_fixture


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def public_link_url(clan_id):
    return reverse('clan-public-link', kwargs={'clan_id': clan_id})


def clan_detail_url(clan_id):
    return reverse('clan-detail', kwargs={'clan_id': clan_id})


class EnablePublicLinkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_public_link_enable')
        cls.clan = cls.fixture['clan']

    def test_owner_can_enable_and_gets_slug_and_url(self):
        response = client_for(self.fixture['owner']).post(public_link_url(self.clan.id))
        self.assertEqual(200, response.status_code)
        data = response.json()['data']
        self.assertTrue(data['slug'])
        self.assertIn(data['slug'], data['url'])

        self.clan.refresh_from_db()
        self.assertEqual('public_link', self.clan.visibility)
        self.assertEqual(data['slug'], self.clan.public_slug)
        # 22 chars per `services.public_slug.generate_public_slug`, well
        # under the column's max_length=32.
        self.assertEqual(22, len(self.clan.public_slug))

    def test_editor_cannot_enable(self):
        response = client_for(self.fixture['editor']).post(public_link_url(self.clan.id))
        self.assertEqual(403, response.status_code)

    def test_viewer_cannot_enable(self):
        response = client_for(self.fixture['viewer']).post(public_link_url(self.clan.id))
        self.assertEqual(403, response.status_code)

    def test_outsider_gets_404_not_403(self):
        response = client_for(self.fixture['outsider']).post(public_link_url(self.clan.id))
        self.assertEqual(404, response.status_code)

    def test_unknown_clan_is_404(self):
        response = client_for(self.fixture['owner']).post(public_link_url(999999))
        self.assertEqual(404, response.status_code)

    def test_re_enabling_issues_a_different_slug(self):
        client = client_for(self.fixture['owner'])
        first = client.post(public_link_url(self.clan.id)).json()['data']['slug']
        client.delete(public_link_url(self.clan.id))
        second = client.post(public_link_url(self.clan.id)).json()['data']['slug']
        self.assertNotEqual(first, second)


class RevokePublicLinkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_public_link_revoke')
        cls.clan = cls.fixture['clan']

    def setUp(self):
        # `test_revoke_kills_the_old_slug_immediately` hits the throttled
        # public-facing `giapha-public` scope; clear it so an earlier test
        # class's requests (same IP, same process-wide cache) never carry
        # over and falsely trip 429 here.
        cache.clear()
        client_for(self.fixture['owner']).post(public_link_url(self.clan.id))
        self.clan.refresh_from_db()
        self.old_slug = self.clan.public_slug

    def test_owner_can_revoke(self):
        response = client_for(self.fixture['owner']).delete(public_link_url(self.clan.id))
        self.assertEqual(204, response.status_code)

        self.clan.refresh_from_db()
        self.assertEqual('private', self.clan.visibility)
        self.assertIsNone(self.clan.public_slug)

    def test_revoke_kills_the_old_slug_immediately(self):
        client_for(self.fixture['owner']).delete(public_link_url(self.clan.id))
        response = self.client.get(reverse('public-clan-tree', kwargs={'slug': self.old_slug}))
        self.assertEqual(404, response.status_code)

    def test_editor_cannot_revoke(self):
        response = client_for(self.fixture['editor']).delete(public_link_url(self.clan.id))
        self.assertEqual(403, response.status_code)
        clan = Clan.objects.get(id=self.clan.id)
        self.assertEqual('public_link', clan.visibility)


class PatchCannotToggleVisibilityTests(TestCase):
    """Regression for H2 (phase-9 security review): `visibility` used to be
    writable through `PATCH /clans/{id}` (`ClanDetailAPIView.patch`), a
    second, unguarded way to change sharing state that never touched
    `public_slug`. That let an owner PATCH to `'private'` (looking revoked)
    then PATCH back to `'public_link'` and RE-ARM THE SAME OLD SLUG --
    `DELETE /public-link` is the only path that ever cleared `public_slug`
    alongside `visibility`. `serializers.clan.ClanSerializer` now declares
    `visibility` read-only; `POST`/`DELETE /public-link` are the only ways
    to change it.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_public_link_patch_visibility')
        cls.clan = cls.fixture['clan']

    def setUp(self):
        cache.clear()

    def test_patch_to_private_does_not_change_visibility_or_slug(self):
        owner = client_for(self.fixture['owner'])
        slug = owner.post(public_link_url(self.clan.id)).json()['data']['slug']

        response = owner.patch(clan_detail_url(self.clan.id), {'visibility': 'private'}, format='json')
        self.assertEqual(200, response.status_code)

        self.clan.refresh_from_db()
        self.assertEqual('public_link', self.clan.visibility, 'PATCH must not be able to flip visibility')
        self.assertEqual(slug, self.clan.public_slug, 'PATCH must not touch public_slug either')

        # The slug the PATCH attempt did nothing to must still resolve --
        # proving the attempted "revoke via PATCH" had no effect at all.
        live_response = self.client.get(reverse('public-clan-tree', kwargs={'slug': slug}))
        self.assertEqual(200, live_response.status_code)

    def test_sanctioned_delete_still_revokes_and_reenabling_mints_a_different_slug(self):
        owner = client_for(self.fixture['owner'])
        old_slug = owner.post(public_link_url(self.clan.id)).json()['data']['slug']

        # An attempted PATCH toggle in between -- must be a no-op (asserted
        # above); the sanctioned route must still work regardless.
        owner.patch(clan_detail_url(self.clan.id), {'visibility': 'private'}, format='json')

        revoke_response = owner.delete(public_link_url(self.clan.id))
        self.assertEqual(204, revoke_response.status_code)

        old_slug_response = self.client.get(reverse('public-clan-tree', kwargs={'slug': old_slug}))
        self.assertEqual(404, old_slug_response.status_code, 'the sanctioned DELETE must still revoke')

        new_slug = owner.post(public_link_url(self.clan.id)).json()['data']['slug']
        self.assertNotEqual(old_slug, new_slug, 're-enabling must mint a fresh slug, never restore the old one')
