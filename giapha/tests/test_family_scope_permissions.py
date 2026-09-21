"""Row-level write scope on `/clans` persons, marriages and photos (plan
260919 phase 1): role x in/out of family scope x verified/unverified.
"""

from unittest import mock

from django.test import TestCase
from django.urls import reverse

from giapha.models import ClanMember, Marriage, Person
from giapha.permissions_scope import OUT_OF_SCOPE_DETAIL
from giapha.tests.scope_helpers import build_scoped_clan, client_for


def person_url(clan, person):
    return reverse('person-detail', kwargs={'clan_id': clan.id, 'person_id': person.id})


class VerifiedViewerScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_scope')
        cls.clan = cls.fx['clan']

    def patch(self, user, person, body=None):
        return client_for(user).patch(person_url(self.clan, person), body or {'nghe_nghiep': 'Nông'}, format='json')

    def test_viewer_edits_own_family(self):
        for key in ('self_node', 'vo', 'con', 'cha', 'me', 'em'):
            with self.subTest(person=key):
                self.assertEqual(200, self.patch(self.fx['viewer'], self.fx[key]).status_code)

    def test_viewer_cannot_edit_outside_scope_and_gets_proposal_hint(self):
        for key in ('ong', 'ba', 'bac', 'con_bac'):
            with self.subTest(person=key):
                response = self.patch(self.fx['viewer'], self.fx[key])
                self.assertEqual(403, response.status_code)
                self.assertEqual(OUT_OF_SCOPE_DETAIL, response.json()['detail'])

    def test_verified_sibling_leaves_scope(self):
        from giapha.tests.scope_helpers import add_member
        add_member(self.clan, 'em_user_scope', 'viewer', person=self.fx['em'], verified=True)
        self.assertEqual(403, self.patch(self.fx['viewer'], self.fx['em']).status_code)

    def test_unverified_viewer_edits_nothing(self):
        ClanMember.objects.filter(user=self.fx['viewer']).update(person_verified=False)
        for key in ('self_node', 'con'):
            with self.subTest(person=key):
                self.assertEqual(403, self.patch(self.fx['viewer'], self.fx[key]).status_code)

    def test_unbound_viewer_cannot_delete(self):
        ClanMember.objects.filter(user=self.fx['viewer']).update(person=None, person_verified=False)
        response = client_for(self.fx['viewer']).delete(person_url(self.clan, self.fx['con']))
        self.assertEqual(403, response.status_code)

    def test_editor_manager_owner_edit_everyone(self):
        for role in ('owner', 'manager', 'editor'):
            with self.subTest(role=role):
                self.assertEqual(200, self.patch(self.fx[role], self.fx['ong']).status_code)

    def test_viewer_deletes_in_scope_person(self):
        grandchild = Person.objects.create(clan=self.clan, ho_ten='Cháu', gioi_tinh='nam', father=self.fx['con'])
        response = client_for(self.fx['viewer']).delete(person_url(self.clan, grandchild))
        self.assertEqual(204, response.status_code)

    def test_viewer_force_is_still_owner_only(self):
        url = person_url(self.clan, self.fx['con']) + '?force=true'
        response = client_for(self.fx['viewer']).patch(url, {'nghe_nghiep': 'x'}, format='json')
        self.assertEqual(403, response.status_code)

    def test_viewer_cannot_read_revisions_or_restore(self):
        url = reverse('person-revisions', kwargs={'clan_id': self.clan.id, 'person_id': self.fx['con'].id})
        self.assertEqual(403, client_for(self.fx['viewer']).get(url).status_code)


class CreateAndMarriageScopeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_scope_create')
        cls.clan = cls.fx['clan']

    def post_person(self, body):
        url = reverse('person-list-create', kwargs={'clan_id': self.clan.id})
        return client_for(self.fx['viewer']).post(url, body, format='json')

    def test_add_child_under_own_node(self):
        response = self.post_person({'ho_ten': 'Con út', 'gioi_tinh': 'nam', 'father_id': self.fx['self_node'].id})
        self.assertEqual(201, response.status_code)

    def test_add_child_under_uncle_is_forbidden(self):
        response = self.post_person({'ho_ten': 'Con bác 2', 'gioi_tinh': 'nam', 'father_id': self.fx['bac'].id})
        self.assertEqual(403, response.status_code)

    def test_parentless_person_is_forbidden_for_viewer(self):
        self.assertEqual(403, self.post_person({'ho_ten': 'Lạ', 'gioi_tinh': 'nam'}).status_code)

    def test_bulk_with_one_item_out_of_scope_writes_nothing(self):
        before = Person.objects.filter(clan=self.clan).count()
        response = self.post_person([
            {'ho_ten': 'A', 'gioi_tinh': 'nam', 'father_id': self.fx['self_node'].id},
            {'ho_ten': 'B', 'gioi_tinh': 'nam', 'father_id': self.fx['bac'].id},
        ])
        self.assertEqual(403, response.status_code)
        self.assertEqual(before, Person.objects.filter(clan=self.clan).count())

    def test_marriage_needs_one_partner_in_scope(self):
        url = reverse('marriage-list-create', kwargs={'clan_id': self.clan.id})
        wife = Person.objects.create(clan=self.clan, ho_ten='Dâu', gioi_tinh='nu')
        ok = client_for(self.fx['viewer']).post(
            url, {'husband_id': self.fx['con'].id, 'wife_id': wife.id, 'status': 'dang_ket_hon'}, format='json')
        self.assertEqual(201, ok.status_code)
        other = Person.objects.create(clan=self.clan, ho_ten='Vợ bác', gioi_tinh='nu')
        denied = client_for(self.fx['viewer']).post(
            url, {'husband_id': self.fx['bac'].id, 'wife_id': other.id, 'status': 'dang_ket_hon'}, format='json')
        self.assertEqual(403, denied.status_code)

    def test_marriage_detail_scope(self):
        grandparents = Marriage.objects.get(husband=self.fx['ong'])
        own = Marriage.objects.get(husband=self.fx['self_node'])
        viewer = client_for(self.fx['viewer'])

        def url(marriage):
            return reverse('marriage-detail', kwargs={'clan_id': self.clan.id, 'marriage_id': marriage.id})
        self.assertEqual(403, viewer.patch(url(grandparents), {'note': 'x'}, format='json').status_code)
        self.assertEqual(403, viewer.delete(url(grandparents)).status_code)
        self.assertEqual(200, viewer.patch(url(own), {'note': 'x'}, format='json').status_code)

    @mock.patch('giapha.services.storage.presign_put', return_value='https://example/put')
    @mock.patch('giapha.services.storage.is_configured', return_value=True)
    def test_photo_endpoints_follow_scope(self, _configured, _presign):
        viewer = client_for(self.fx['viewer'])

        def url(name, person):
            return reverse(name, kwargs={'clan_id': self.clan.id, 'person_id': person.id})
        body = {'content_type': 'image/jpeg', 'size': 1000}
        self.assertEqual(200, viewer.post(url('person-photo-upload-url', self.fx['con']), body, format='json').status_code)
        self.assertEqual(403, viewer.post(url('person-photo-upload-url', self.fx['ong']), body, format='json').status_code)
        self.assertEqual(403, viewer.delete(url('person-photo', self.fx['ong'])).status_code)


class CanEditAndTreeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_scope_ui')
        cls.clan = cls.fx['clan']

    def test_person_detail_can_edit(self):
        viewer = client_for(self.fx['viewer'])
        self.assertEqual('direct', viewer.get(person_url(self.clan, self.fx['con'])).json()['data']['can_edit'])
        self.assertEqual('propose', viewer.get(person_url(self.clan, self.fx['ong'])).json()['data']['can_edit'])
        editor = client_for(self.fx['editor'])
        self.assertEqual('direct', editor.get(person_url(self.clan, self.fx['ong'])).json()['data']['can_edit'])

    def test_tree_my_editable_ids(self):
        url = reverse('clan-tree', kwargs={'clan_id': self.clan.id})
        self.assertIsNone(client_for(self.fx['editor']).get(url).json()['my_editable_ids'])
        ids = set(client_for(self.fx['viewer']).get(url).json()['my_editable_ids'])
        expected = {self.fx[k].id for k in ('self_node', 'vo', 'con', 'cha', 'me', 'em')}
        self.assertEqual(expected, ids)
