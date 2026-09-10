"""Cross-user isolation for `/v1/family`: an id from ANOTHER user's family
must never be read, linked, or written through any endpoint -- it is either
`PERSON_NOT_FOUND` (404) or a `DANGLING_*` rule error (400), and the other
family's rows stay untouched. Pins what `require_person`/`graph.has` guard.
"""

from django.test import TestCase

from giapha.models import FamilyPerson, FamilySpouse
from giapha.tests.family_helpers import client_for, family_of, make_person, make_user, relation, url


class FamilyIsolationTests(TestCase):
    def setUp(self):
        self.user = make_user('fam_iso_me')
        self.client = client_for(self.user)
        self.family = family_of(self.user)
        self.mine = make_person(self.family, 'Của tôi', 'male')

        stranger = make_user('fam_iso_stranger')
        self.theirs_family = family_of(stranger)
        self.theirs = make_person(self.theirs_family, 'Của họ', 'female')
        self.their_kid = make_person(self.theirs_family, 'Con họ', father=None)

    def assertUntouched(self):
        self.theirs.refresh_from_db()
        self.their_kid.refresh_from_db()
        self.assertIsNone(self.theirs.father_id)
        self.assertIsNone(self.theirs.mother_id)
        self.assertIsNone(self.their_kid.father_id)
        self.assertIsNone(self.their_kid.mother_id)
        self.assertFalse(FamilySpouse.objects.exists())
        self.assertTrue(FamilyPerson.objects.filter(id=self.theirs.id).exists())

    def assertRejected(self, response, codes):
        self.assertIn(response.status_code, (400, 404), response.content)
        self.assertIn(response.json()['error']['code'], codes)

    def test_person_endpoints_reject_foreign_ids(self):
        detail = url('family-person-detail', person_id=self.theirs.id)
        self.assertRejected(self.client.get(detail), {'PERSON_NOT_FOUND'})
        self.assertRejected(self.client.patch(detail, {'name': 'Hack'}, format='json'), {'PERSON_NOT_FOUND'})
        self.assertRejected(self.client.delete(detail), {'PERSON_NOT_FOUND'})
        self.assertRejected(
            self.client.put(url('family-person-gio-event', person_id=self.theirs.id), {'eventId': 'x'}, format='json'),
            {'PERSON_NOT_FOUND'},
        )
        self.assertRejected(
            self.client.put(url('family-self'), {'personId': str(self.theirs.id)}, format='json'),
            {'PERSON_NOT_FOUND'},
        )
        self.theirs.refresh_from_db()
        self.assertEqual(self.theirs.name, 'Của họ')
        self.assertUntouched()

    def test_relation_endpoints_reject_foreign_ids_in_every_position(self):
        mine, theirs, kid = str(self.mine.id), str(self.theirs.id), str(self.their_kid.id)
        attempts = (
            ('family-set-parent', {'childId': mine, 'slot': 'mother', 'parentId': theirs}, {'DANGLING_MOTHER'}),
            ('family-set-parent', {'childId': theirs, 'slot': 'father', 'parentId': mine}, {'PERSON_NOT_FOUND'}),
            ('family-link-spouse', {'aId': mine, 'bId': theirs}, {'DANGLING_SPOUSE'}),
            ('family-link-spouse', {'aId': theirs, 'bId': mine}, {'PERSON_NOT_FOUND'}),
            ('family-unlink-spouse', {'aId': mine, 'bId': theirs}, {'PERSON_NOT_FOUND'}),
            ('family-link-child', {'parentId': mine, 'childId': kid}, {'PERSON_NOT_FOUND'}),
            ('family-link-child', {'parentId': theirs, 'childId': mine}, {'PERSON_NOT_FOUND'}),
            ('family-add-relative', {'anchorId': theirs, 'kind': 'child', 'person': {'name': 'X'}}, {'PERSON_NOT_FOUND'}),
        )
        for name, body, codes in attempts:
            self.assertRejected(relation(self.client, name, body), codes)
        self.assertUntouched()
        self.mine.refresh_from_db()
        self.assertIsNone(self.mine.mother_id)
        self.assertEqual(FamilyPerson.objects.filter(family=self.family).count(), 1)

    def test_foreign_other_parent_is_ignored_with_a_warning(self):
        kid = make_person(self.family, 'Con')
        body = relation(self.client, 'family-link-child', {
            'parentId': str(self.mine.id), 'childId': str(kid.id), 'otherParentId': str(self.theirs.id),
        }).json()
        self.assertTrue(body['ok'])
        self.assertIsNone(body['person']['motherId'])
        self.assertEqual(body['warning']['code'], 'OTHER_PARENT_NOT_CANDIDATE')
        self.assertUntouched()

    def test_family_full_blocks_creation(self):
        with self.settings(FAMILY_MAX_PERSONS=1):
            response = self.client.post(url('family-person-create'), {'name': 'Thứ hai'}, format='json')
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()['error']['code'], 'FAMILY_FULL')
            response = relation(self.client, 'family-add-relative', {
                'anchorId': str(self.mine.id), 'kind': 'spouse', 'person': {'name': 'Vợ'},
            })
            self.assertEqual(response.json()['error']['code'], 'FAMILY_FULL')
        self.assertEqual(FamilyPerson.objects.filter(family=self.family).count(), 1)
