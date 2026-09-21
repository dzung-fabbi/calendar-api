"""Editing a linked person from the personal tree (plan 260919 phase 5)."""

from unittest import mock

from django.test import TestCase
from django.urls import reverse

from giapha.models import ChangeRequest, FamilyPerson, FamilyPersonLink, Person
from giapha.tests.family_helpers import family_of, make_person
from giapha.tests.scope_helpers import build_scoped_clan, client_for


def link(user, family_person, clan, clan_person):
    FamilyPersonLink.objects.create(family=family_of(user), family_person=family_person,
                                    clan=clan, clan_person=clan_person, linked_by=user)


class LinkedEditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_linked_edit')
        cls.clan = cls.fx['clan']
        cls.user = cls.fx['viewer']
        family = family_of(cls.user)
        cls.f_ong = make_person(family, 'Ông', 'male')
        cls.f_con = make_person(family, 'Con', 'male')
        link(cls.user, cls.f_ong, cls.clan, cls.fx['ong'])
        link(cls.user, cls.f_con, cls.clan, cls.fx['con'])

    def patch(self, person, body):
        url = reverse('family-person-detail', kwargs={'person_id': person.id})
        return client_for(self.user).patch(url, body, format='json')

    @mock.patch('giapha.views.change_request.push_to_users')
    def test_out_of_scope_name_becomes_proposal_and_note_saves(self, _push):
        response = self.patch(self.f_ong, {'name': 'Cụ Ông', 'note': 'ghi chú của tôi'})
        self.assertEqual(200, response.status_code, response.content)
        writes = response.json()['clanWrites']
        self.assertEqual('proposed', writes[0]['result'])
        cr = ChangeRequest.objects.get(id=writes[0]['changeRequestId'])
        self.assertEqual('update_person', cr.action)
        self.assertEqual(1, cr.base_version)
        self.assertEqual('Ông', Person.objects.get(id=self.fx['ong'].id).ho_ten)
        self.assertEqual('ghi chú của tôi', FamilyPerson.objects.get(id=self.f_ong.id).note)

    def test_in_scope_applies_and_version_conflict_reported(self):
        applied = self.patch(self.f_con, {'name': 'Con Cả', 'clanVersions': {str(self.clan.id): 1}}).json()
        self.assertEqual('applied', applied['clanWrites'][0]['result'])
        self.assertEqual('Con Cả', Person.objects.get(id=self.fx['con'].id).ho_ten)
        conflict = self.patch(self.f_con, {'name': 'Con Út', 'note': 'n',
                                           'clanVersions': {str(self.clan.id): 1}}).json()
        self.assertEqual('conflict', conflict['clanWrites'][0]['result'])
        self.assertEqual('Con Cả', conflict['clanWrites'][0]['current']['ho_ten'])
        self.assertEqual('n', FamilyPerson.objects.get(id=self.f_con.id).note)

    def test_private_only_edit_touches_no_clan(self):
        body = self.patch(self.f_ong, {'relationship': 'Ông nội'}).json()
        self.assertEqual([], body['clanWrites'])
        self.assertFalse(ChangeRequest.objects.exists())

    def test_set_parent_in_personal_tree_does_not_touch_clan(self):
        before = Person.objects.get(id=self.fx['con'].id)
        client_for(self.user).post(reverse('family-set-parent'), {
            'childId': str(self.f_con.id), 'slot': 'father', 'parentId': str(self.f_ong.id),
        }, format='json')
        after = Person.objects.get(id=self.fx['con'].id)
        self.assertEqual((before.father_id, before.version), (after.father_id, after.version))


class AddRelativeContributeToTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_contrib_to')
        cls.clan = cls.fx['clan']
        cls.user = cls.fx['viewer']
        cls.f_con = make_person(family_of(cls.user), 'Con', 'male')
        link(cls.user, cls.f_con, cls.clan, cls.fx['con'])

    def test_new_child_is_contributed_under_linked_parent(self):
        response = client_for(self.user).post(reverse('family-add-relative'), {
            'anchorId': str(self.f_con.id), 'kind': 'child',
            'person': {'name': 'Cháu nội', 'gender': 'male'}, 'contributeTo': [self.clan.id],
        }, format='json')
        self.assertEqual(200, response.status_code, response.content)
        contribution = response.json()['contributions'][0]
        self.assertEqual('applied', contribution['result'])
        self.assertEqual(self.fx['con'].id, Person.objects.get(id=contribution['clanPersonId']).father_id)
