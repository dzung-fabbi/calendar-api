"""Personal tree <-> clan links end to end (plan 260919 phase 4)."""

from unittest import mock

from django.test import TestCase
from django.urls import reverse

from giapha.models import ChangeRequest, ClanMember, FamilyPerson, FamilyPersonLink, Person
from giapha.tests.family_helpers import family_of, make_person, make_spouse
from giapha.tests.scope_helpers import build_scoped_clan, client_for


def root_of(user):
    return client_for(user).get(reverse('family-root')).json()


def by_id(body, person_id):
    return next(p for p in body['persons'] if p['id'] == str(person_id))


class LinkOverlayAndDetachTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_link')
        cls.clan = cls.fx['clan']
        cls.user = cls.fx['viewer']
        cls.family = family_of(cls.user)
        cls.f_ong = make_person(cls.family, 'Ông nội (tên cũ)', 'male', note='riêng tư')
        cls.f_me = make_person(cls.family, 'Tôi', 'male')

    def link(self, person, clan_person):
        return client_for(self.user).post(reverse('family-links'), {
            'clanId': self.clan.id, 'pairs': [{'personId': str(person.id), 'clanPersonId': clan_person.id}],
        }, format='json')

    def test_linked_person_reads_shared_fields_from_clan(self):
        self.assertEqual(201, self.link(self.f_ong, self.fx['ong']).status_code)
        Person.objects.filter(id=self.fx['ong'].id).update(ho_ten='Ông Tổ Mới')
        body = root_of(self.user)
        person = by_id(body, self.f_ong.id)
        self.assertEqual('Ông Tổ Mới', person['name'])
        self.assertEqual('riêng tư', person['note'])
        self.assertTrue(person['linked'])
        self.assertEqual(self.clan.id, body['links'][0]['clanId'])
        self.assertFalse(by_id(body, self.f_me.id)['linked'])

    def test_duplicate_link_is_conflict(self):
        self.link(self.f_ong, self.fx['ong'])
        self.assertEqual(400, self.link(self.f_me, self.fx['ong']).status_code)

    def test_non_member_gets_404(self):
        response = client_for(self.fx['outsider']).get(reverse('family-link-suggestions'), {'clanId': self.clan.id})
        self.assertEqual(404, response.status_code)

    def test_detach_keeps_last_clan_values(self):
        self.link(self.f_ong, self.fx['ong'])
        link = FamilyPersonLink.objects.get()
        response = client_for(self.user).delete(reverse('family-link-detail', kwargs={'link_id': link.id}))
        self.assertEqual(200, response.status_code)
        self.assertEqual('Ông', FamilyPerson.objects.get(id=self.f_ong.id).name)
        self.assertFalse(FamilyPersonLink.objects.exists())

    def test_removed_from_clan_auto_detaches_without_data_loss(self):
        self.link(self.f_ong, self.fx['ong'])
        url = reverse('clan-member-detail', kwargs={'clan_id': self.clan.id, 'user_id': self.user.id})
        self.assertEqual(204, client_for(self.fx['owner']).delete(url).status_code)
        self.assertFalse(FamilyPersonLink.objects.exists())
        self.assertEqual('Ông', FamilyPerson.objects.get(id=self.f_ong.id).name)

    def test_clan_person_soft_delete_and_clan_delete_detach(self):
        self.link(self.f_me, self.fx['con_bac'])
        client_for(self.fx['owner']).delete(
            reverse('person-detail', kwargs={'clan_id': self.clan.id, 'person_id': self.fx['con_bac'].id}))
        self.assertFalse(FamilyPersonLink.objects.exists())
        self.link(self.f_ong, self.fx['ong'])
        client_for(self.fx['owner']).delete(reverse('clan-detail', kwargs={'clan_id': self.clan.id}))
        self.assertFalse(FamilyPersonLink.objects.exists())

    def test_suggestions_never_create_links_and_empty_tree_asks_import(self):
        response = client_for(self.user).get(reverse('family-link-suggestions'), {'clanId': self.clan.id})
        self.assertEqual(200, response.status_code)
        self.assertFalse(FamilyPersonLink.objects.exists())
        other = self.fx['editor']
        empty = client_for(other).get(reverse('family-link-suggestions'), {'clanId': self.clan.id}).json()
        self.assertTrue(empty['importRequired'])

    def test_diff_lists_structure_mismatch(self):
        self.link(self.f_me, self.fx['self_node'])
        diffs = client_for(self.user).get(reverse('family-link-diff'), {'clanId': self.clan.id}).json()['diffs']
        self.assertIn('father', {item['field'] for item in diffs})


class ImportAndContributeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_link_flow')
        cls.clan = cls.fx['clan']
        cls.user = cls.fx['viewer']
        cls.family = family_of(cls.user)

    def test_import_creates_linked_people_with_edges(self):
        ids = [self.fx[key].id for key in ('ong', 'ba', 'cha')]
        response = client_for(self.user).post(reverse('family-link-import'),
                                              {'clanId': self.clan.id, 'clanPersonIds': ids}, format='json')
        self.assertEqual(201, response.status_code, response.content)
        body = response.json()
        imported = body['imported']
        cha = by_id(body, imported[str(self.fx['cha'].id)])
        self.assertEqual(imported[str(self.fx['ong'].id)], cha['fatherId'])
        self.assertEqual(imported[str(self.fx['ba'].id)], cha['motherId'])
        ong = by_id(body, imported[str(self.fx['ong'].id)])
        self.assertEqual([imported[str(self.fx['ba'].id)]], [s['id'] for s in ong['spouses']])
        self.assertEqual(3, FamilyPersonLink.objects.count())

    def test_contribute_in_scope_applies_and_links(self):
        child = make_person(self.family, 'Cháu mới', 'male')
        response = client_for(self.user).post(reverse('family-link-contribute'), {
            'personId': str(child.id), 'clanId': self.clan.id, 'fatherClanPersonId': self.fx['con'].id,
        }, format='json')
        self.assertEqual(201, response.status_code, response.content)
        clan_person = Person.objects.get(id=response.json()['clanPersonId'])
        self.assertEqual(self.fx['con'].id, clan_person.father_id)
        self.assertTrue(FamilyPersonLink.objects.filter(family_person=child, clan_person=clan_person).exists())

    @mock.patch('giapha.views.change_request.push_to_users')
    def test_contribute_out_of_scope_proposes_then_links_on_approval(self, _push):
        cousin_child = make_person(self.family, 'Con của anh họ', 'female')
        response = client_for(self.user).post(reverse('family-link-contribute'), {
            'personId': str(cousin_child.id), 'clanId': self.clan.id, 'fatherClanPersonId': self.fx['con_bac'].id,
        }, format='json')
        self.assertEqual(202, response.status_code, response.content)
        cr_id = response.json()['changeRequestId']
        self.assertEqual(cousin_child.id, ChangeRequest.objects.get(id=cr_id).family_person_id)

        url = reverse('change-request-approve', kwargs={'clan_id': self.clan.id, 'cr_id': cr_id})
        self.assertEqual(200, client_for(self.fx['editor']).post(url, {}, format='json').status_code)
        link = FamilyPersonLink.objects.get(family_person=cousin_child)
        self.assertEqual(self.fx['con_bac'].id, link.clan_person.father_id)


class BootstrapClanTests(TestCase):
    def test_bootstrap_copies_branch_links_and_binds_owner(self):
        from giapha.tests.family_helpers import make_user
        user = make_user('bootstrapper')
        family = family_of(user)
        grandpa = make_person(family, 'Cụ', 'male', deceased=True)
        grandma = make_person(family, 'Cụ bà', 'female')
        me = make_person(family, 'Tôi', 'male', father=grandpa, mother=grandma)
        make_spouse(family, grandpa, grandma)
        family.self_person = me
        family.save()

        response = client_for(user).post(reverse('family-clan-bootstrap'),
                                         {'rootPersonId': str(grandpa.id), 'tenHo': 'Họ Mới'}, format='json')
        self.assertEqual(201, response.status_code, response.content)
        clan_id = response.json()['clan']['id']
        self.assertEqual(3, Person.objects.filter(clan_id=clan_id).count())
        member = ClanMember.objects.get(clan_id=clan_id, user=user)
        self.assertEqual('owner', member.role)
        self.assertTrue(member.person_verified)
        clan_me = Person.objects.get(id=member.person_id)
        self.assertEqual('Cụ', clan_me.father.ho_ten)
        self.assertTrue(Person.objects.get(clan_id=clan_id, ho_ten='Cụ').da_mat)
        self.assertEqual(3, FamilyPersonLink.objects.filter(clan_id=clan_id).count())
        self.assertTrue(all(p['linked'] for p in response.json()['persons']))
