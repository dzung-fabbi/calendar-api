"""Branch editors -- trưởng chi (plan 260919 phase 6).

Uses `build_scoped_clan`: branch 1 = `bac` (+ `con_bac`), branch 2 = `cha`
(+ me, `em`, my wife and child). The `editor` user is made trưởng chi 2.
"""

from unittest import mock

from django.test import TestCase
from django.urls import reverse

from giapha.models import ChangeRequest, ClanMember
from giapha.tests.scope_helpers import add_member, build_scoped_clan, client_for


class BranchEditorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_branch')
        cls.clan = cls.fx['clan']
        ClanMember.objects.filter(user=cls.fx['editor']).update(scope_root_person=cls.fx['cha'])

    def patch(self, user, key):
        url = reverse('person-detail', kwargs={'clan_id': self.clan.id, 'person_id': self.fx[key].id})
        return client_for(user).patch(url, {'nghe_nghiep': 'x'}, format='json')

    def test_branch_editor_edits_only_own_branch(self):
        for key in ('cha', 'me', 'self_node', 'con', 'em'):
            with self.subTest(person=key):
                self.assertEqual(200, self.patch(self.fx['editor'], key).status_code)
        for key in ('bac', 'con_bac', 'ong'):
            with self.subTest(person=key):
                self.assertEqual(403, self.patch(self.fx['editor'], key).status_code)

    def test_owner_and_manager_unaffected(self):
        self.assertEqual(200, self.patch(self.fx['owner'], 'bac').status_code)
        self.assertEqual(200, self.patch(self.fx['manager'], 'bac').status_code)

    def test_tree_editable_ids_is_the_branch(self):
        ids = client_for(self.fx['editor']).get(
            reverse('clan-tree', kwargs={'clan_id': self.clan.id})).json()['my_editable_ids']
        self.assertEqual({self.fx[k].id for k in ('cha', 'me', 'self_node', 'vo', 'con', 'em')}, set(ids))

    @mock.patch('giapha.views.change_request.push_to_users')
    def test_change_requests_routed_by_branch(self, push):
        list_url = reverse('change-request-list-create', kwargs={'clan_id': self.clan.id})
        other = add_member(self.clan, 'branch_other_viewer', 'viewer')
        branch1 = client_for(other).post(list_url, {
            'action': 'update_person', 'target_person_id': self.fx['con_bac'].id, 'payload': {'nghe_nghiep': 'y'},
        }, format='json').json()['data']
        self.assertNotIn(self.fx['editor'].id, push.call_args[0][0])
        self.assertIn(self.fx['owner'].id, push.call_args[0][0])

        queue = client_for(self.fx['editor']).get(list_url).json()['data']
        self.assertNotIn(branch1['id'], [cr['id'] for cr in queue])
        approve = reverse('change-request-approve', kwargs={'clan_id': self.clan.id, 'cr_id': branch1['id']})
        self.assertEqual(403, client_for(self.fx['editor']).post(approve, {}, format='json').status_code)

        branch2 = client_for(other).post(list_url, {
            'action': 'update_person', 'target_person_id': self.fx['em'].id, 'payload': {'nghe_nghiep': 'z'},
        }, format='json').json()['data']
        self.assertIn(self.fx['editor'].id, push.call_args[0][0])
        approve2 = reverse('change-request-approve', kwargs={'clan_id': self.clan.id, 'cr_id': branch2['id']})
        self.assertEqual(200, client_for(self.fx['editor']).post(approve2, {}, format='json').status_code)
        self.assertEqual('approved', ChangeRequest.objects.get(id=branch2['id']).status)

    def test_branch_editor_verifies_inside_branch_only(self):
        inside = add_member(self.clan, 'claims_em', 'viewer', person=self.fx['em'])
        outside = add_member(self.clan, 'claims_con_bac', 'viewer', person=self.fx['con_bac'])
        editor = client_for(self.fx['editor'])

        def url(user):
            return reverse('clan-member-verify', kwargs={'clan_id': self.clan.id, 'user_id': user.id})
        self.assertEqual(200, editor.post(url(inside)).status_code)
        self.assertEqual(403, editor.post(url(outside)).status_code)


class MemberScopePatchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_branch_patch')
        cls.clan = cls.fx['clan']

    def patch(self, user, body):
        url = reverse('clan-member-detail', kwargs={'clan_id': self.clan.id, 'user_id': user.id})
        return client_for(self.fx['owner']).patch(url, body, format='json')

    def test_owner_sets_and_clears_branch(self):
        response = self.patch(self.fx['editor'], {'scope_root_person_id': self.fx['bac'].id})
        self.assertEqual(200, response.status_code)
        self.assertEqual(self.fx['bac'].id, response.json()['data']['scope_root_person_id'])
        self.patch(self.fx['editor'], {'role': 'viewer'})
        self.assertIsNone(ClanMember.objects.get(user=self.fx['editor']).scope_root_person_id)

    def test_scope_for_manager_or_unknown_root_is_400(self):
        self.assertEqual(400, self.patch(self.fx['manager'], {'scope_root_person_id': self.fx['bac'].id}).status_code)
        self.assertEqual(400, self.patch(self.fx['editor'], {'scope_root_person_id': 999999}).status_code)
        self.assertEqual(400, self.patch(self.fx['editor'], {}).status_code)

    def test_manager_cannot_set_scope(self):
        url = reverse('clan-member-detail', kwargs={'clan_id': self.clan.id, 'user_id': self.fx['editor'].id})
        response = client_for(self.fx['manager']).patch(url, {'scope_root_person_id': self.fx['bac'].id}, format='json')
        self.assertEqual(403, response.status_code)
