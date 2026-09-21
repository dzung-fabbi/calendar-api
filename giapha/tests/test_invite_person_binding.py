"""Join with a person-bound invite, `toi-la` verification state and the
verify/reject endpoints (plan 260919 phase 1).
"""

from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from giapha.models import ClanInvite, ClanMember
from giapha.tests.scope_helpers import build_scoped_clan, client_for


def join(user, code):
    return client_for(user).post(reverse('clan-join'), {'code': code}, format='json')


class JoinBindsInvitedPersonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_join_bind')
        cls.clan = cls.fx['clan']

    def invite_for(self, person, code):
        return ClanInvite.objects.create(clan=self.clan, code=code, role='viewer', person=person, max_uses=1)

    def test_join_binds_and_verifies(self):
        self.invite_for(self.fx['con'], 'BINDCON01')
        response = join(self.fx['outsider'], 'BINDCON01')
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(self.fx['con'].id, body['binding']['person_id'])
        self.assertTrue(body['binding']['person_verified'])
        member = ClanMember.objects.get(clan=self.clan, user=self.fx['outsider'])
        self.assertEqual(self.fx['con'].id, member.person_id)
        self.assertTrue(member.person_verified)

    def test_two_invites_same_node_only_first_binds(self):
        self.invite_for(self.fx['em'], 'BINDEM001')
        self.invite_for(self.fx['em'], 'BINDEM002')
        second_user = User.objects.create_user(username='second_join_user', password='pw')
        self.assertIsNotNone(join(self.fx['outsider'], 'BINDEM001').json()['binding'])
        response = join(second_user, 'BINDEM002')
        self.assertEqual(200, response.status_code)
        self.assertIsNone(response.json()['binding'])
        self.assertIn('message', response.json())
        self.assertTrue(ClanMember.objects.filter(clan=self.clan, user=second_user, person__isnull=True).exists())

    def test_plain_invite_join_has_null_binding(self):
        ClanInvite.objects.create(clan=self.clan, code='PLAINJOIN1', role='viewer')
        body = join(self.fx['outsider'], 'PLAINJOIN1').json()
        self.assertIsNone(body['binding'])
        self.assertNotIn('message', body)


class ToiLaVerificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_toila', verified=False)
        cls.clan = cls.fx['clan']
        ClanMember.objects.filter(user=cls.fx['viewer']).update(person=None)

    def put(self, user, person):
        url = reverse('clan-toi-la', kwargs={'clan_id': self.clan.id})
        return client_for(user).put(url, {'person_id': person.id}, format='json')

    @mock.patch('giapha.views.member_binding.push_to_users')
    def test_viewer_claim_is_unverified_and_pushes_approvers(self, push):
        response = self.put(self.fx['viewer'], self.fx['con'])
        self.assertEqual(200, response.status_code)
        self.assertFalse(response.json()['data']['person_verified'])
        self.assertEqual({self.fx['owner'].id, self.fx['manager'].id}, set(push.call_args[0][0]))

    def test_unverified_claim_grants_no_write(self):
        self.put(self.fx['viewer'], self.fx['self_node'])
        url = reverse('person-detail', kwargs={'clan_id': self.clan.id, 'person_id': self.fx['con'].id})
        response = client_for(self.fx['viewer']).patch(url, {'nghe_nghiep': 'x'}, format='json')
        self.assertEqual(403, response.status_code)

    def test_editor_claim_is_verified(self):
        self.assertTrue(self.put(self.fx['editor'], self.fx['bac']).json()['data']['person_verified'])

    def test_rebinding_elsewhere_drops_verification(self):
        ClanMember.objects.filter(user=self.fx['viewer']).update(person=self.fx['self_node'], person_verified=True)
        self.assertTrue(self.put(self.fx['viewer'], self.fx['self_node']).json()['data']['person_verified'])
        self.assertFalse(self.put(self.fx['viewer'], self.fx['em']).json()['data']['person_verified'])


class VerifyEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_verify', verified=False)
        cls.clan = cls.fx['clan']

    def url(self):
        return reverse('clan-member-verify', kwargs={'clan_id': self.clan.id, 'user_id': self.fx['viewer'].id})

    def test_editor_cannot_verify(self):
        self.assertEqual(403, client_for(self.fx['editor']).post(self.url()).status_code)

    def test_owner_and_manager_verify(self):
        for role in ('owner', 'manager'):
            with self.subTest(role=role):
                ClanMember.objects.filter(user=self.fx['viewer']).update(person_verified=False)
                response = client_for(self.fx[role]).post(self.url())
                self.assertEqual(200, response.status_code)
                self.assertTrue(response.json()['data']['person_verified'])

    def test_verified_viewer_can_then_edit(self):
        client_for(self.fx['owner']).post(self.url())
        url = reverse('person-detail', kwargs={'clan_id': self.clan.id, 'person_id': self.fx['con'].id})
        self.assertEqual(200, client_for(self.fx['viewer']).patch(url, {'nghe_nghiep': 'x'}, format='json').status_code)

    def test_reject_removes_binding(self):
        response = client_for(self.fx['manager']).delete(self.url())
        self.assertEqual(200, response.status_code)
        member = ClanMember.objects.get(user=self.fx['viewer'], clan=self.clan)
        self.assertIsNone(member.person_id)
        self.assertFalse(member.person_verified)

    def test_unbound_member_is_400(self):
        url = reverse('clan-member-verify', kwargs={'clan_id': self.clan.id, 'user_id': self.fx['editor'].id})
        self.assertEqual(400, client_for(self.fx['owner']).post(url).status_code)
