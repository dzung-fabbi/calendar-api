"""API tests for `/v1/family` read, person CRUD, "tôi" and gio-event --
spec §8.1/8.2/8.4/8.5 and the §13 checklist items they own.
"""

from django.test import TestCase

from giapha.models import Family, FamilyPerson, FamilySpouse
from giapha.serializers.family_output import PERSON_KEYS
from giapha.tests.family_helpers import (
    client_for,
    family_of,
    make_person,
    make_spouse,
    make_user,
    person_by_id,
    url,
)


class FamilyReadTests(TestCase):
    def setUp(self):
        self.user = make_user('fam_read')
        self.client = client_for(self.user)

    def test_first_get_creates_an_empty_family(self):
        self.assertFalse(Family.objects.filter(user=self.user).exists())
        response = self.client.get(url('family-root'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'selfId': None, 'persons': []})
        self.assertTrue(Family.objects.filter(user=self.user).exists())

    def test_unauthenticated_is_rejected(self):
        from rest_framework.test import APIClient
        response = APIClient().get(url('family-root'))
        self.assertIn(response.status_code, (401, 403))

    def test_persons_carry_the_exact_wire_shape_with_spouses_both_ways(self):
        family = family_of(self.user)
        me = make_person(family, 'Tôi', 'male')
        wife = make_person(family, 'Vợ', 'female')
        make_spouse(family, me, wife)
        family.self_person = me
        family.save()

        body = self.client.get(url('family-root')).json()
        self.assertEqual(body['selfId'], str(me.id))
        self.assertEqual(len(body['persons']), 2)
        for person in body['persons']:
            self.assertEqual(set(person.keys()), set(PERSON_KEYS))
        self.assertEqual(person_by_id(body['persons'], me.id)['spouses'], [{'id': str(wife.id), 'type': 'married'}])
        self.assertEqual(person_by_id(body['persons'], wife.id)['spouses'], [{'id': str(me.id), 'type': 'married'}])

    def test_other_users_family_is_invisible(self):
        other = make_user('fam_read_other')
        stranger = make_person(family_of(other), 'Người lạ')
        response = self.client.get(url('family-person-detail', person_id=stranger.id))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error']['code'], 'PERSON_NOT_FOUND')
        self.assertEqual(self.client.get(url('family-root')).json()['persons'], [])


class PersonCreateTests(TestCase):
    def setUp(self):
        self.user = make_user('fam_create')
        self.client = client_for(self.user)

    def test_name_is_the_only_required_field_and_defaults_match_spec(self):
        response = self.client.post(url('family-person-create'), {'name': '  Nguyễn Văn A '}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertTrue(body['ok'])
        self.assertFalse(body['linked'])
        self.assertIsNone(body['hint'])
        person = body['person']
        self.assertEqual(person['name'], 'Nguyễn Văn A')
        self.assertEqual(person['gender'], 'unknown')
        self.assertFalse(person['deceased'])
        self.assertEqual(person['spouses'], [])
        self.assertIsNone(person['fatherId'])
        self.assertIsInstance(person['createdAt'], int)
        self.assertEqual(len(body['persons']), 1)

    def test_blank_name_is_a_validation_error_with_code_and_message(self):
        response = self.client.post(url('family-person-create'), {'name': '   '}, format='json')
        self.assertEqual(response.status_code, 400)
        error = response.json()['error']
        self.assertEqual(error['code'], 'VALIDATION')
        self.assertEqual(error['message'], 'Tên không được để trống.')
        self.assertIn('name', error['fields'])

    def test_dates_and_times_use_the_app_formats(self):
        response = self.client.post(url('family-person-create'), {
            'name': 'Cụ', 'gender': 'male', 'deceased': True,
            'solarBirthDate': '05-03-1920', 'birthTime': '07:30',
            'lunarDeathDay': 1, 'lunarDeathMonth': 1, 'lunarDeathYear': 2024, 'deathTime': '23:15',
            'relationship': 'Cụ / Tổ tiên', 'note': 'ghi chú',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        person = response.json()['person']
        self.assertEqual(person['solarBirthDate'], '05-03-1920')
        self.assertEqual(person['birthTime'], '07:30')
        # Derived from the complete lunar date: mùng 1 Tết Giáp Thìn.
        self.assertEqual(person['solarDeathDate'], '10-02-2024')
        self.assertEqual(person['deathTime'], '23:15')
        self.assertEqual(person['relationship'], 'Cụ / Tổ tiên')

    def test_lunar_death_without_year_keeps_the_mark_but_no_solar_date(self):
        response = self.client.post(url('family-person-create'), {
            'name': 'Bà', 'deceased': True, 'lunarDeathDay': 20, 'lunarDeathMonth': 12,
        }, format='json')
        person = response.json()['person']
        self.assertEqual((person['lunarDeathDay'], person['lunarDeathMonth']), (20, 12))
        self.assertIsNone(person['lunarDeathYear'])
        self.assertIsNone(person['solarDeathDate'])

    def test_out_of_range_lunar_values_and_bad_time_are_rejected(self):
        for payload in (
            {'name': 'X', 'lunarDeathDay': 0},
            {'name': 'X', 'lunarDeathMonth': 13},
            {'name': 'X', 'birthTime': '08'},
            {'name': 'X', 'solarBirthDate': '1990-01-05'},
        ):
            response = self.client.post(url('family-person-create'), payload, format='json')
            self.assertEqual(response.status_code, 400, payload)
            self.assertEqual(response.json()['error']['code'], 'VALIDATION')

    def test_deceased_does_not_require_a_death_date(self):
        response = self.client.post(url('family-person-create'), {'name': 'Cụ', 'deceased': True}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['person']['deceased'])

    def test_relationship_edges_in_the_body_are_ignored(self):
        other = make_person(family_of(self.user), 'Ai đó', 'male')
        response = self.client.post(url('family-person-create'), {
            'name': 'B', 'fatherId': str(other.id), 'spouses': [{'id': str(other.id), 'type': 'married'}],
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()['person']['fatherId'])
        self.assertEqual(response.json()['person']['spouses'], [])


class PersonAutoLinkByLabelTests(TestCase):
    def setUp(self):
        self.user = make_user('fam_label')
        self.client = client_for(self.user)
        self.family = family_of(self.user)
        self.me = make_person(self.family, 'Tôi', 'male')
        self.family.self_person = self.me
        self.family.save()

    def create(self, **payload):
        return self.client.post(url('family-person-create'), payload, format='json').json()

    def test_cha_links_as_father_of_self(self):
        body = self.create(name='Cha tôi', gender='male', relationship='Cha')
        self.assertTrue(body['linked'])
        self.me.refresh_from_db()
        self.assertEqual(str(self.me.father_id), body['person']['id'])

    def test_second_cha_is_saved_but_not_linked_with_a_hint(self):
        self.create(name='Cha', gender='male', relationship='Cha')
        body = self.create(name='Cha khác', gender='male', relationship='Cha')
        self.assertFalse(body['linked'])
        self.assertIn('đã khai Cha', body['hint'])
        self.assertEqual(FamilyPerson.objects.filter(family=self.family).count(), 3)

    def test_ong_ngoai_without_mother_gives_hint(self):
        body = self.create(name='Ông ngoại', gender='male', relationship='Ông ngoại')
        self.assertFalse(body['linked'])
        self.assertIn('Chưa có Mẹ', body['hint'])

    def test_vo_links_spouse_and_fills_first_spouse_into_children(self):
        kid = make_person(self.family, 'Con', father=self.me)
        body = self.create(name='Vợ', gender='female', relationship='Vợ')
        self.assertTrue(body['linked'])
        self.assertEqual(person_by_id(body['persons'], self.me.id)['spouses'][0]['id'], body['person']['id'])
        self.assertEqual(person_by_id(body['persons'], kid.id)['motherId'], body['person']['id'])

    def test_con_links_child_under_self(self):
        body = self.create(name='Con', relationship='Con')
        self.assertTrue(body['linked'])
        self.assertEqual(body['person']['fatherId'], str(self.me.id))

    def test_em_copies_parents_when_self_has_one(self):
        no_parents = self.create(name='Em', relationship='Em')
        self.assertFalse(no_parents['linked'])
        self.assertIn('anh chị em', no_parents['hint'])
        self.create(name='Cha', gender='male', relationship='Cha')
        body = self.create(name='Em', relationship='Em')
        self.assertTrue(body['linked'])
        self.me.refresh_from_db()
        self.assertEqual(body['person']['fatherId'], str(self.me.father_id))

    def test_ambiguous_label_saves_unlinked_without_hint(self):
        body = self.create(name='Cháu', relationship='Cháu')
        self.assertFalse(body['linked'])
        self.assertIsNone(body['hint'])
        self.assertEqual(body['person']['relationship'], 'Cháu')


class PersonPatchDeleteTests(TestCase):
    def setUp(self):
        self.user = make_user('fam_patch')
        self.client = client_for(self.user)
        self.family = family_of(self.user)
        self.grandpa = make_person(self.family, 'Ông', 'male')
        self.dad = make_person(self.family, 'Cha', 'male', father=self.grandpa)
        self.mom = make_person(self.family, 'Mẹ', 'female')
        self.me = make_person(self.family, 'Tôi', 'male', father=self.dad, mother=self.mom)
        make_spouse(self.family, self.dad, self.mom)

    def test_patch_changes_info_but_never_edges(self):
        response = self.client.patch(url('family-person-detail', person_id=self.me.id), {
            'name': 'Tôi mới', 'fatherId': None, 'motherId': str(self.grandpa.id), 'spouses': [],
        }, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        person = response.json()['person']
        self.assertEqual(person['name'], 'Tôi mới')
        self.assertEqual(person['fatherId'], str(self.dad.id))
        self.assertEqual(person['motherId'], str(self.mom.id))

    def test_patch_rederives_solar_death_from_merged_lunar_fields(self):
        detail = url('family-person-detail', person_id=self.grandpa.id)
        self.client.patch(detail, {'deceased': True, 'lunarDeathDay': 1, 'lunarDeathMonth': 1}, format='json')
        person = self.client.patch(detail, {'lunarDeathYear': 2024}, format='json').json()['person']
        self.assertEqual(person['solarDeathDate'], '10-02-2024')
        person = self.client.patch(detail, {'lunarDeathYear': None}, format='json').json()['person']
        self.assertIsNone(person['solarDeathDate'])

    def test_delete_detaches_without_cascading(self):
        self.family.self_person = self.dad
        self.family.save()
        response = self.client.delete(url('family-person-detail', person_id=self.dad.id))
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertTrue(body['deleted'])
        self.assertEqual(set(body['detachedFrom']), {str(self.me.id), str(self.mom.id)})
        self.assertIsNone(body['selfId'])

        self.me.refresh_from_db()
        self.assertIsNone(self.me.father_id)
        self.assertEqual(self.me.mother_id, self.mom.id)
        self.assertTrue(FamilyPerson.objects.filter(id=self.grandpa.id).exists())
        self.assertFalse(FamilySpouse.objects.filter(person_a=self.dad).exists())
        self.assertFalse(FamilySpouse.objects.filter(person_b=self.dad).exists())

    def test_delete_unknown_is_404_envelope(self):
        import uuid
        response = self.client.delete(url('family-person-detail', person_id=uuid.uuid4()))
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()['ok'])


class SelfAndGioEventTests(TestCase):
    def setUp(self):
        self.user = make_user('fam_self')
        self.client = client_for(self.user)
        self.family = family_of(self.user)
        self.a = make_person(self.family, 'A')
        self.b = make_person(self.family, 'B')

    def put_self(self, person_id):
        return self.client.put(url('family-self'), {'personId': person_id}, format='json')

    def test_set_then_clear_then_set_someone_else(self):
        self.assertEqual(self.put_self(str(self.a.id)).json(), {'selfId': str(self.a.id)})
        taken = self.put_self(str(self.b.id))
        self.assertEqual(taken.status_code, 400)
        self.assertEqual(taken.json()['error']['code'], 'SELF_ALREADY_SET')
        self.assertEqual(self.put_self(str(self.a.id)).status_code, 200)  # re-asserting holder is fine
        self.assertEqual(self.put_self(None).json(), {'selfId': None})
        self.assertEqual(self.put_self(str(self.b.id)).json(), {'selfId': str(self.b.id)})
        self.assertEqual(self.client.get(url('family-root')).json()['selfId'], str(self.b.id))

    def test_self_must_be_in_my_family(self):
        stranger = make_person(family_of(make_user('fam_self_other')), 'X')
        self.assertEqual(self.put_self(str(stranger.id)).status_code, 404)

    def test_gio_event_is_stored_and_cleared(self):
        endpoint = url('family-person-gio-event', person_id=self.a.id)
        body = self.client.put(endpoint, {'eventId': 'evt_123'}, format='json').json()
        self.assertEqual(body['person']['gioEventId'], 'evt_123')
        body = self.client.put(endpoint, {'eventId': None}, format='json').json()
        self.assertIsNone(body['person']['gioEventId'])
