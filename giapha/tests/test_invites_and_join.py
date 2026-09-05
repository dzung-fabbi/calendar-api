"""Invite issuing/listing/revocation, redemption (join), the last-owner
guard, and the `/join` throttle scope.
"""

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from djangopj.settings import REST_FRAMEWORK
from giapha.models import ClanInvite, ClanMember
from giapha.tests.factories import build_clan_fixture


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def invites_url(clan_id):
    return reverse('clan-invite-create', kwargs={'clan_id': clan_id})


def invite_detail_url(clan_id, invite_id):
    return reverse('clan-invite-detail', kwargs={'clan_id': clan_id, 'invite_id': invite_id})


class JoinClanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']

    def join(self, user, code):
        return client_for(user).post(reverse('clan-join'), {'code': code}, format='json')

    def test_valid_code_creates_membership(self):
        invite = ClanInvite.objects.create(clan=self.clan, code='VALIDCODE', role='viewer')
        new_user = self.fixture['outsider']

        response = self.join(new_user, invite.code)
        self.assertEqual(200, response.status_code)
        self.assertTrue(ClanMember.objects.filter(clan=self.clan, user=new_user, role='viewer').exists())
        invite.refresh_from_db()
        self.assertEqual(1, invite.used_count)

    def test_unknown_code_is_rejected(self):
        response = self.join(self.fixture['outsider'], 'NOSUCHCODE')
        self.assertEqual(404, response.status_code)

    def test_expired_code_is_rejected(self):
        invite = ClanInvite.objects.create(
            clan=self.clan, code='EXPIREDONE', role='viewer',
            expires_at=timezone.now() - timezone.timedelta(days=1),
        )
        response = self.join(self.fixture['outsider'], invite.code)
        self.assertEqual(400, response.status_code)
        self.assertFalse(ClanMember.objects.filter(clan=self.clan, user=self.fixture['outsider']).exists())

    def test_over_max_uses_code_is_rejected(self):
        invite = ClanInvite.objects.create(
            clan=self.clan, code='MAXEDOUT01', role='viewer', max_uses=1, used_count=1,
        )
        response = self.join(self.fixture['outsider'], invite.code)
        self.assertEqual(400, response.status_code)

    def test_joining_twice_with_same_code_is_idempotent(self):
        invite = ClanInvite.objects.create(clan=self.clan, code='REJOINABLE', role='viewer')
        new_user = self.fixture['outsider']

        first = self.join(new_user, invite.code)
        second = self.join(new_user, invite.code)

        self.assertEqual(200, first.status_code)
        self.assertEqual(200, second.status_code)
        self.assertEqual(1, ClanMember.objects.filter(clan=self.clan, user=new_user).count())
        invite.refresh_from_db()
        self.assertEqual(1, invite.used_count, 'rejoining must not consume a second use')

    def test_already_a_member_can_rejoin_even_if_code_now_exhausted(self):
        """Rejoining is a no-op regardless of the code's current state --
        only *new* redemptions are checked against expiry/exhaustion."""
        invite = ClanInvite.objects.create(
            clan=self.clan, code='STILLGOOD1', role='viewer', max_uses=1, used_count=1,
        )
        response = self.join(self.fixture['viewer'], invite.code)
        self.assertEqual(200, response.status_code)

    def test_missing_code_is_a_400(self):
        response = client_for(self.fixture['outsider']).post(reverse('clan-join'), {}, format='json')
        self.assertEqual(400, response.status_code)


class LastOwnerGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']

    def member_url(self, user_id):
        return reverse('clan-member-detail', kwargs={'clan_id': self.clan.id, 'user_id': user_id})

    def test_cannot_demote_the_only_owner(self):
        response = client_for(self.fixture['owner']).patch(
            self.member_url(self.fixture['owner'].id), {'role': 'editor'}, format='json',
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual(
            'owner', ClanMember.objects.get(clan=self.clan, user=self.fixture['owner']).role,
        )

    def test_cannot_remove_the_only_owner(self):
        response = client_for(self.fixture['owner']).delete(self.member_url(self.fixture['owner'].id))
        self.assertEqual(400, response.status_code)
        self.assertTrue(ClanMember.objects.filter(clan=self.clan, user=self.fixture['owner']).exists())

    def test_can_demote_an_owner_when_another_owner_remains(self):
        second_owner = self.fixture['editor']
        ClanMember.objects.filter(clan=self.clan, user=second_owner).update(role='owner')

        response = client_for(self.fixture['owner']).patch(
            self.member_url(self.fixture['owner'].id), {'role': 'editor'}, format='json',
        )
        self.assertEqual(200, response.status_code)


class InviteCreateTests(TestCase):
    """Product decisions: invite roles are capped to editor/viewer, and
    `expires_at` always resolves to a real datetime 30 days out.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_invcreate')
        cls.clan = cls.fixture['clan']

    def test_role_defaults_to_viewer(self):
        response = client_for(self.fixture['owner']).post(invites_url(self.clan.id), {}, format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual('viewer', response.json()['data']['role'])

    def test_editor_role_is_grantable(self):
        response = client_for(self.fixture['owner']).post(
            invites_url(self.clan.id), {'role': 'editor'}, format='json',
        )
        self.assertEqual(201, response.status_code)
        self.assertEqual('editor', response.json()['data']['role'])

    def test_owner_role_is_not_grantable_through_an_invite(self):
        """Product decision 1: ownership transfer is a separate owner-only
        action (`PATCH /clans/{id}/members/{user_id}`), never reachable
        through a redeemable code.
        """
        response = client_for(self.fixture['owner']).post(
            invites_url(self.clan.id), {'role': 'owner'}, format='json',
        )
        self.assertEqual(400, response.status_code)
        self.assertFalse(ClanInvite.objects.filter(clan=self.clan, role='owner').exists())

    def test_expires_at_defaults_to_thirty_days_out(self):
        before = timezone.now()
        response = client_for(self.fixture['owner']).post(invites_url(self.clan.id), {}, format='json')
        after = timezone.now()
        self.assertEqual(201, response.status_code)

        invite = ClanInvite.objects.get(code=response.json()['data']['code'])
        self.assertIsNotNone(invite.expires_at, 'expires_at must never default to None (never-expiring)')
        self.assertGreaterEqual(invite.expires_at, before + timezone.timedelta(days=29))
        self.assertLessEqual(invite.expires_at, after + timezone.timedelta(days=31))

    def test_max_uses_still_defaults_to_unlimited(self):
        response = client_for(self.fixture['owner']).post(invites_url(self.clan.id), {}, format='json')
        self.assertEqual(0, response.json()['data']['max_uses'])

    def test_explicit_expires_at_is_respected(self):
        custom = (timezone.now() + timezone.timedelta(days=1)).isoformat()
        response = client_for(self.fixture['owner']).post(
            invites_url(self.clan.id), {'expires_at': custom}, format='json',
        )
        self.assertEqual(201, response.status_code)


class InviteListAndRevokeTests(TestCase):
    """Product decision 3: a leaked invite code must have a remediation
    path -- list it, then revoke it.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_invlist')
        cls.clan = cls.fixture['clan']

    def setUp(self):
        self.invite = ClanInvite.objects.create(clan=self.clan, code='LISTME01', role='viewer')

    def test_owner_can_list_invites(self):
        response = client_for(self.fixture['owner']).get(invites_url(self.clan.id))
        self.assertEqual(200, response.status_code)
        codes = {row['code'] for row in response.json()['data']}
        self.assertIn('LISTME01', codes)

    def test_editor_and_viewer_cannot_list_invites(self):
        for role in ('editor', 'viewer'):
            with self.subTest(role=role):
                response = client_for(self.fixture[role]).get(invites_url(self.clan.id))
                self.assertEqual(403, response.status_code)

    def test_outsider_gets_404_on_invite_list(self):
        response = client_for(self.fixture['outsider']).get(invites_url(self.clan.id))
        self.assertEqual(404, response.status_code)

    def test_owner_can_revoke_an_invite(self):
        response = client_for(self.fixture['owner']).delete(
            invite_detail_url(self.clan.id, self.invite.id),
        )
        self.assertEqual(204, response.status_code)
        self.assertFalse(ClanInvite.objects.filter(id=self.invite.id).exists())

    def test_revoked_invite_can_no_longer_be_joined(self):
        client_for(self.fixture['owner']).delete(invite_detail_url(self.clan.id, self.invite.id))

        response = client_for(self.fixture['outsider']).post(
            reverse('clan-join'), {'code': self.invite.code}, format='json',
        )
        self.assertEqual(404, response.status_code)

    def test_editor_cannot_revoke_an_invite(self):
        response = client_for(self.fixture['editor']).delete(
            invite_detail_url(self.clan.id, self.invite.id),
        )
        self.assertEqual(403, response.status_code)
        self.assertTrue(ClanInvite.objects.filter(id=self.invite.id).exists())

    def test_revoking_unknown_invite_is_404(self):
        response = client_for(self.fixture['owner']).delete(
            invite_detail_url(self.clan.id, 999999),
        )
        self.assertEqual(404, response.status_code)


class JoinThrottleTests(TestCase):
    """Product decision 5: only `/join` is throttled.

    `ScopedRateThrottle.THROTTLE_RATES` is bound from `api_settings` at
    CLASS-DEFINITION time (module import), so `override_settings` on
    `REST_FRAMEWORK` cannot change it for an already-imported throttle class
    -- this test exercises the real configured rate
    (`settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['giapha-join']`)
    directly instead of trying to override it.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_throttle')

    def setUp(self):
        cache.clear()

    def test_repeated_join_attempts_are_eventually_throttled(self):
        limit = int(REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['giapha-join'].split('/')[0])
        client = client_for(self.fixture['outsider'])
        statuses = [
            client.post(reverse('clan-join'), {'code': 'NOSUCHCODE'}, format='json').status_code
            for _ in range(limit + 1)
        ]
        self.assertNotIn(429, statuses[:limit], 'requests within the configured rate must not be throttled')
        self.assertEqual(429, statuses[-1], 'the request past the configured rate must be throttled')

    def test_other_endpoints_are_not_throttled_by_the_join_scope(self):
        """Decision 5: throttling must stay scoped to `/join` only -- another
        endpoint hit the same number of times (well past the join limit)
        must never see a 429.
        """
        limit = int(REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['giapha-join'].split('/')[0])
        client = client_for(self.fixture['owner'])
        clan_id = self.fixture['clan'].id
        statuses = [
            client.get(reverse('clan-detail', kwargs={'clan_id': clan_id})).status_code
            for _ in range(limit + 5)
        ]
        self.assertNotIn(429, statuses)


class InviteRoleIsCappedAtRedemptionTests(TestCase):
    """An invite must never grant ownership -- and the serializer that caps
    new invites at INVITE_ROLE is bypassed entirely by Django admin, so the
    check has to exist at the line that actually grants the role.
    """

    def setUp(self):
        self.fixture = build_clan_fixture()
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_owner_role_cannot_be_requested_through_the_api(self):
        client = client_for(self.fixture['owner'])
        response = client.post(
            reverse('clan-invite-create', kwargs={'clan_id': self.fixture['clan'].id}),
            {'role': 'owner'},
            format='json',
        )
        self.assertEqual(400, response.status_code)

    def test_owner_invite_written_outside_the_api_is_refused_at_join(self):
        """Simulates a row created through Django admin, which never touches
        the serializer. Redeeming it must fail closed rather than hand out
        ownership of the clan.
        """
        invite = ClanInvite.objects.create(
            clan=self.fixture['clan'], code='ADMINOWN', role='owner',
            expires_at=timezone.now() + timezone.timedelta(days=1),
        )
        outsider = self.fixture['outsider']
        response = client_for(outsider).post(
            reverse('clan-join'), {'code': invite.code}, format='json',
        )
        self.assertEqual(400, response.status_code)
        self.assertFalse(
            ClanMember.objects.filter(clan=self.fixture['clan'], user=outsider).exists(),
            'a refused invite must not create membership of any role',
        )
