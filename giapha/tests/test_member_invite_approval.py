"""Member-issued invites, approval by owner/manager, manager limits (plan
260919 phase 1).
"""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from giapha.models import ClanInvite, ClanMember
from giapha.tests.scope_helpers import build_scoped_clan, client_for


def invites_url(clan):
    return reverse('clan-invite-create', kwargs={'clan_id': clan.id})


def review_url(clan, invite, action):
    return reverse('clan-invite-' + action, kwargs={'clan_id': clan.id, 'invite_id': invite.id})


class MemberInviteCreateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_inv')
        cls.clan = cls.fx['clan']

    def setUp(self):
        cache.clear()  # throttle buckets

    def create(self, user, **body):
        return client_for(user).post(invites_url(self.clan), body, format='json')

    def test_verified_member_inviting_own_child_is_active_with_code(self):
        response = self.create(self.fx['viewer'], person_id=self.fx['con'].id)
        self.assertEqual(201, response.status_code)
        data = response.json()['data']
        self.assertEqual('active', data['status'])
        self.assertTrue(data['code'])
        self.assertEqual(1, data['max_uses'])

    @mock.patch('giapha.views.clan_invite.push_to_users')
    def test_inviting_uncle_is_pending_without_code_and_pushes_approvers(self, push):
        response = self.create(self.fx['viewer'], person_id=self.fx['bac'].id, request_note='Bác tôi')
        data = response.json()['data']
        self.assertEqual('pending_approval', data['status'])
        self.assertIsNone(data['code'])
        self.assertEqual('Bác tôi', data['request_note'])
        pushed_to = set(push.call_args[0][0])
        self.assertEqual({self.fx['owner'].id, self.fx['manager'].id}, pushed_to)

    def test_invite_without_person_is_pending(self):
        self.assertEqual('pending_approval', self.create(self.fx['viewer']).json()['data']['status'])

    def test_member_editor_role_invite_is_always_pending(self):
        data = self.create(self.fx['editor'], role='editor', person_id=self.fx['con'].id).json()['data']
        self.assertEqual('pending_approval', data['status'])

    def test_unverified_member_cannot_invite(self):
        ClanMember.objects.filter(user=self.fx['viewer']).update(person_verified=False)
        self.assertEqual(403, self.create(self.fx['viewer'], person_id=self.fx['con'].id).status_code)

    def test_person_must_be_alive_unclaimed_and_in_clan(self):
        self.fx['ong'].death_solar = '1990-01-01'
        self.fx['ong'].save()
        self.assertEqual(400, self.create(self.fx['owner'], person_id=self.fx['ong'].id).status_code)
        self.assertEqual(400, self.create(self.fx['owner'], person_id=self.fx['self_node'].id).status_code)
        self.assertEqual(400, self.create(self.fx['owner'], person_id=999999).status_code)

    def test_member_open_invite_cap(self):
        for _ in range(10):
            self.assertEqual(201, self.create(self.fx['viewer']).status_code)
        self.assertEqual(400, self.create(self.fx['viewer']).status_code)

    def test_member_lists_only_own_and_approver_filters_by_status(self):
        self.create(self.fx['viewer'])
        self.create(self.fx['owner'])
        own = client_for(self.fx['viewer']).get(invites_url(self.clan)).json()['data']
        self.assertEqual(1, len(own))
        pending = client_for(self.fx['manager']).get(invites_url(self.clan), {'status': 'pending_approval'})
        self.assertEqual(1, len(pending.json()['data']))

    def test_delete_by_creator_or_owner_only(self):
        invite_id = self.create(self.fx['viewer']).json()['data']['id']
        url = reverse('clan-invite-detail', kwargs={'clan_id': self.clan.id, 'invite_id': invite_id})
        self.assertEqual(403, client_for(self.fx['manager']).delete(url).status_code)
        self.assertEqual(204, client_for(self.fx['viewer']).delete(url).status_code)


class InviteReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_inv_review')
        cls.clan = cls.fx['clan']

    def pending(self, role='viewer'):
        return ClanInvite.objects.create(
            clan=self.clan, role=role, status='pending_approval', created_by=self.fx['viewer'],
        )

    @mock.patch('giapha.views.invite_review.push_to_users')
    def test_owner_approves_mints_code_and_pushes_inviter(self, push):
        invite = self.pending()
        response = client_for(self.fx['owner']).post(review_url(self.clan, invite, 'approve'), {}, format='json')
        self.assertEqual(200, response.status_code)
        invite.refresh_from_db()
        self.assertEqual('active', invite.status)
        self.assertTrue(invite.code)
        self.assertEqual(self.fx['owner'], invite.approved_by)
        self.assertEqual([self.fx['viewer'].id], push.call_args[0][0])

    @mock.patch('giapha.views.invite_review.push_to_users')
    def test_reject_keeps_no_code_and_sends_reason(self, push):
        invite = self.pending()
        client_for(self.fx['manager']).post(review_url(self.clan, invite, 'reject'), {'note': 'Không rõ'}, format='json')
        invite.refresh_from_db()
        self.assertEqual('rejected', invite.status)
        self.assertIsNone(invite.code)
        self.assertIn('Không rõ', push.call_args[0][2])

    def test_editor_cannot_review(self):
        invite = self.pending()
        response = client_for(self.fx['editor']).post(review_url(self.clan, invite, 'approve'), {}, format='json')
        self.assertEqual(403, response.status_code)

    def test_manager_approves_viewer_invite_but_not_editor_invite(self):
        viewer_invite, editor_invite = self.pending('viewer'), self.pending('editor')
        manager = client_for(self.fx['manager'])
        self.assertEqual(200, manager.post(review_url(self.clan, viewer_invite, 'approve'), {}, format='json').status_code)
        self.assertEqual(403, manager.post(review_url(self.clan, editor_invite, 'approve'), {}, format='json').status_code)

    def test_non_pending_invite_cannot_be_reviewed_twice(self):
        invite = self.pending()
        owner = client_for(self.fx['owner'])
        owner.post(review_url(self.clan, invite, 'approve'), {}, format='json')
        self.assertEqual(400, owner.post(review_url(self.clan, invite, 'reject'), {}, format='json').status_code)

    def test_pending_invite_cannot_be_redeemed(self):
        invite = self.pending()
        invite.code = 'SNEAKY01'  # admin-edited row: code but still pending
        invite.save()
        response = client_for(self.fx['outsider']).post(reverse('clan-join'), {'code': 'SNEAKY01'}, format='json')
        self.assertEqual(404, response.status_code)


class ManagerLimitsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_mgr')
        cls.clan = cls.fx['clan']

    def test_manager_cannot_change_roles_remove_members_or_share_publicly(self):
        manager = client_for(self.fx['manager'])
        member_url = reverse('clan-member-detail', kwargs={'clan_id': self.clan.id, 'user_id': self.fx['viewer'].id})
        self.assertEqual(403, manager.patch(member_url, {'role': 'editor'}, format='json').status_code)
        self.assertEqual(403, manager.delete(member_url).status_code)
        public_url = reverse('clan-public-link', kwargs={'clan_id': self.clan.id})
        self.assertEqual(403, manager.post(public_url, {}, format='json').status_code)
        clan_url = reverse('clan-detail', kwargs={'clan_id': self.clan.id})
        self.assertEqual(403, manager.patch(clan_url, {'ten_ho': 'x'}, format='json').status_code)

    def test_only_owner_assigns_manager(self):
        url = reverse('clan-member-detail', kwargs={'clan_id': self.clan.id, 'user_id': self.fx['editor'].id})
        self.assertEqual(200, client_for(self.fx['owner']).patch(url, {'role': 'manager'}, format='json').status_code)
        self.assertEqual('manager', ClanMember.objects.get(user=self.fx['editor']).role)

    def test_invite_can_never_grant_manager(self):
        response = client_for(self.fx['owner']).post(invites_url(self.clan), {'role': 'manager'}, format='json')
        self.assertEqual(400, response.status_code)
