"""API tests for `POST /v1/family/relations/*` -- spec §4 / §8.3 and the §13
checklist items about edges. Each test builds the tree it needs through the
ORM (fast) and exercises ONE mutation through HTTP.
"""

import uuid

from django.test import TestCase

from giapha.models import FamilyPerson, FamilySpouse
from giapha.tests.family_helpers import (
    client_for,
    family_of,
    make_person,
    make_spouse,
    make_user,
    person_by_id,
    relation,
    url,
)


class _RelationTestCase(TestCase):
    username = 'fam_rel'

    def setUp(self):
        self.user = make_user(self.username)
        self.client = client_for(self.user)
        self.family = family_of(self.user)

    def person(self, name, gender='unknown', **overrides):
        return make_person(self.family, name, gender, **overrides)

    def assertError(self, response, code, status=400):
        self.assertEqual(response.status_code, status, response.content)
        body = response.json()
        self.assertFalse(body['ok'])
        self.assertEqual(body['error']['code'], code)
        self.assertTrue(body['error']['message'])
        return body['error']


class SetParentTests(_RelationTestCase):
    username = 'fam_set_parent'

    def test_set_and_clear_father(self):
        dad, kid = self.person('Cha', 'male'), self.person('Con')
        body = relation(self.client, 'family-set-parent', {
            'childId': str(kid.id), 'slot': 'father', 'parentId': str(dad.id), 'rel': 'adopted',
        }).json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['person']['fatherId'], str(dad.id))
        self.assertEqual(body['person']['fatherRel'], 'adopted')
        self.assertIsNone(body['warning'])

        body = relation(self.client, 'family-set-parent', {
            'childId': str(kid.id), 'slot': 'father', 'parentId': None,
        }).json()
        self.assertIsNone(body['person']['fatherId'])
        self.assertIsNone(body['person']['fatherRel'])

    def test_blood_rel_is_stored_as_null(self):
        mom, kid = self.person('Mẹ', 'female'), self.person('Con')
        body = relation(self.client, 'family-set-parent', {
            'childId': str(kid.id), 'slot': 'mother', 'parentId': str(mom.id),
        }).json()
        self.assertIsNone(body['person']['motherRel'])

    def test_grandchild_as_father_of_grandfather_is_a_cycle(self):
        grandpa = self.person('Ông', 'male')
        dad = self.person('Cha', 'male', father=grandpa)
        me = self.person('Tôi', 'male', father=dad)
        error = self.assertError(relation(self.client, 'family-set-parent', {
            'childId': str(grandpa.id), 'slot': 'father', 'parentId': str(me.id),
        }), 'PARENT_CYCLE')
        self.assertEqual(error['personId'], str(grandpa.id))
        self.assertEqual(error['otherId'], str(me.id))
        grandpa.refresh_from_db()
        self.assertIsNone(grandpa.father_id)

    def test_self_parent_gender_mismatch_and_dangling(self):
        me = self.person('Tôi', 'male')
        woman = self.person('Bà', 'female')
        self.assertError(relation(self.client, 'family-set-parent', {
            'childId': str(me.id), 'slot': 'father', 'parentId': str(me.id),
        }), 'SELF_PARENT')
        self.assertError(relation(self.client, 'family-set-parent', {
            'childId': str(me.id), 'slot': 'father', 'parentId': str(woman.id),
        }), 'GENDER_MISMATCH')
        self.assertError(relation(self.client, 'family-set-parent', {
            'childId': str(me.id), 'slot': 'mother', 'parentId': str(uuid.uuid4()),
        }), 'DANGLING_MOTHER')
        self.assertError(relation(self.client, 'family-set-parent', {
            'childId': str(uuid.uuid4()), 'slot': 'mother', 'parentId': None,
        }), 'PERSON_NOT_FOUND', status=404)

    def test_malformed_body_is_a_validation_envelope(self):
        error = self.assertError(relation(self.client, 'family-set-parent', {'childId': 'abc'}), 'VALIDATION')
        self.assertIn('slot', error['fields'])


class SpouseTests(_RelationTestCase):
    username = 'fam_spouse'

    def link(self, a, b, **extra):
        body = {'aId': str(a.id), 'bId': str(b.id)}
        body.update(extra)
        return relation(self.client, 'family-link-spouse', body)

    def test_link_is_symmetric_and_unlink_stays_unlinked(self):
        me, wife = self.person('Tôi', 'male'), self.person('Vợ', 'female')
        body = self.link(me, wife).json()
        self.assertEqual(person_by_id(body['persons'], me.id)['spouses'], [{'id': str(wife.id), 'type': 'married'}])
        self.assertEqual(person_by_id(body['persons'], wife.id)['spouses'], [{'id': str(me.id), 'type': 'married'}])
        self.assertEqual(FamilySpouse.objects.count(), 1)

        # Re-linking the same pair (either order) updates the type, no duplicate row.
        body = relation(self.client, 'family-link-spouse', {
            'aId': str(wife.id), 'bId': str(me.id), 'type': 'divorced',
        }).json()
        self.assertEqual(FamilySpouse.objects.count(), 1)
        self.assertEqual(person_by_id(body['persons'], me.id)['spouses'][0]['type'], 'divorced')

        relation(self.client, 'family-unlink-spouse', {'aId': str(wife.id), 'bId': str(me.id)})
        persons = self.client.get(url('family-root')).json()['persons']
        self.assertEqual(person_by_id(persons, me.id)['spouses'], [])
        self.assertEqual(person_by_id(persons, wife.id)['spouses'], [])

    def test_first_spouse_fills_missing_mother_of_existing_children(self):
        me = self.person('Tôi', 'male')
        kid = self.person('Con', father=me)
        wife = self.person('Vợ', 'female')
        body = self.link(me, wife).json()
        self.assertEqual(person_by_id(body['persons'], kid.id)['motherId'], str(wife.id))

    def test_second_spouse_does_not_claim_first_wifes_children(self):
        me = self.person('Tôi', 'male')
        wife1 = self.person('Vợ cả', 'female')
        make_spouse(self.family, me, wife1)
        kid = self.person('Con', father=me)  # mother unknown on purpose
        wife2 = self.person('Vợ hai', 'female')
        body = self.link(me, wife2).json()
        self.assertIsNone(person_by_id(body['persons'], kid.id)['motherId'])

    def test_first_spouse_with_wrong_gender_for_the_slot_does_not_fill(self):
        me = self.person('Tôi', 'male')
        kid = self.person('Con', father=me)
        man = self.person('Ông X', 'male')
        body = self.link(me, man).json()
        self.assertIsNone(person_by_id(body['persons'], kid.id)['motherId'])

    def test_lineal_spouse_is_saved_with_a_warning(self):
        dad = self.person('Cha', 'male')
        me = self.person('Tôi', 'female', father=dad)
        body = self.link(dad, me).json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['warning']['code'], 'SPOUSE_IS_ANCESTOR')
        self.assertEqual(FamilySpouse.objects.count(), 1)

    def test_self_spouse_and_dangling(self):
        me = self.person('Tôi')
        self.assertError(self.link(me, me), 'SELF_SPOUSE')
        self.assertError(relation(self.client, 'family-link-spouse', {
            'aId': str(me.id), 'bId': str(uuid.uuid4()),
        }), 'DANGLING_SPOUSE')


class LinkChildTests(_RelationTestCase):
    username = 'fam_link_child'

    def link(self, parent, child, other=None):
        return relation(self.client, 'family-link-child', {
            'parentId': str(parent.id), 'childId': str(child.id), 'otherParentId': other and str(other.id),
        })

    def test_slot_follows_parent_gender_and_unique_partner_is_filled(self):
        dad, mom = self.person('Cha', 'male'), self.person('Mẹ', 'female')
        make_spouse(self.family, dad, mom)
        kid = self.person('Con')
        body = self.link(dad, kid).json()
        self.assertEqual(body['person']['fatherId'], str(dad.id))
        self.assertEqual(body['person']['motherId'], str(mom.id))

    def test_unknown_gender_parent_goes_to_father_slot(self):
        parent, kid = self.person('Người', 'unknown'), self.person('Con')
        body = self.link(parent, kid).json()
        self.assertEqual(body['person']['fatherId'], str(parent.id))

    def test_two_partners_require_an_explicit_choice(self):
        dad = self.person('Cha', 'male')
        wife1, wife2 = self.person('Vợ cả', 'female'), self.person('Vợ hai', 'female')
        make_spouse(self.family, dad, wife1)
        make_spouse(self.family, dad, wife2)
        kid1, kid2 = self.person('Con 1'), self.person('Con 2')
        self.assertIsNone(self.link(dad, kid1).json()['person']['motherId'])
        self.assertEqual(self.link(dad, kid2, other=wife2).json()['person']['motherId'], str(wife2.id))

    def test_co_parent_counts_as_partner(self):
        dad, mom = self.person('Cha', 'male'), self.person('Mẹ', 'female')
        self.person('Con cả', father=dad, mother=mom)  # co-parents, never married
        kid = self.person('Con thứ')
        self.assertEqual(self.link(dad, kid).json()['person']['motherId'], str(mom.id))

    def test_occupied_slot_is_never_overwritten(self):
        dad1, dad2 = self.person('Cha 1', 'male'), self.person('Cha 2', 'male')
        kid = self.person('Con', father=dad1)
        error = self.assertError(self.link(dad2, kid), 'PARENT_SLOT_TAKEN')
        self.assertEqual(error['otherId'], str(dad1.id))
        kid.refresh_from_db()
        self.assertEqual(kid.father_id, dad1.id)


class AddRelativeTests(_RelationTestCase):
    username = 'fam_add_relative'

    def add(self, anchor, kind, person=None, other=None):
        return relation(self.client, 'family-add-relative', {
            'anchorId': str(anchor.id), 'kind': kind,
            'person': person or {'name': 'Mới'}, 'otherParentId': other and str(other.id),
        })

    def test_father_then_mother_are_co_parents_not_spouses(self):
        me = self.person('Tôi', 'male')
        dad = self.add(me, 'father', {'name': 'Cha', 'gender': 'male'}).json()['person']
        mom = self.add(me, 'mother', {'name': 'Mẹ', 'gender': 'female'}).json()['person']
        me.refresh_from_db()
        self.assertEqual(str(me.father_id), dad['id'])
        self.assertEqual(str(me.mother_id), mom['id'])
        self.assertEqual(FamilySpouse.objects.count(), 0)

    def test_second_father_is_rejected_without_creating_an_orphan(self):
        me = self.person('Tôi', 'male')
        self.add(me, 'father', {'name': 'Cha', 'gender': 'male'})
        before = FamilyPerson.objects.count()
        error = self.assertError(self.add(me, 'father', {'name': 'Cha dượng', 'gender': 'male'}), 'PARENT_SLOT_TAKEN')
        self.assertIn('Cha dượng', error['message'])
        self.assertEqual(FamilyPerson.objects.count(), before)

    def test_spouse_kind_links_and_fills_first_spouse(self):
        me = self.person('Tôi', 'male')
        kid = self.person('Con', father=me)
        body = self.add(me, 'spouse', {'name': 'Vợ', 'gender': 'female'}).json()
        self.assertEqual(person_by_id(body['persons'], me.id)['spouses'][0]['id'], body['person']['id'])
        self.assertEqual(person_by_id(body['persons'], kid.id)['motherId'], body['person']['id'])

    def test_child_kind_uses_anchor_gender_and_chosen_other_parent(self):
        mom = self.person('Mẹ', 'female')
        h1, h2 = self.person('Chồng 1', 'male'), self.person('Chồng 2', 'male')
        make_spouse(self.family, mom, h1)
        make_spouse(self.family, mom, h2)
        body = self.add(mom, 'child', {'name': 'Con'}, other=h2).json()
        self.assertEqual(body['person']['motherId'], str(mom.id))
        self.assertEqual(body['person']['fatherId'], str(h2.id))

    def test_sibling_copies_parents_and_is_refused_without_any(self):
        dad = self.person('Cha', 'male')
        me = self.person('Tôi', father=dad)
        body = self.add(me, 'sibling', {'name': 'Em'}).json()
        self.assertEqual(body['person']['fatherId'], str(dad.id))
        self.assertIsNone(body['person']['motherId'])

        orphan = self.person('Lẻ')
        self.assertError(self.add(orphan, 'sibling'), 'NO_PARENT_FOR_SIBLING')

    def test_unknown_anchor_and_bad_draft(self):
        stranger = make_person(family_of(make_user('fam_add_other')), 'X')
        self.assertError(self.add(stranger, 'spouse'), 'PERSON_NOT_FOUND', status=404)
        me = self.person('Tôi')
        error = self.assertError(self.add(me, 'child', {'name': ''}), 'VALIDATION')
        self.assertIn('person', error['fields'])


class DeleteMiddleOfBranchTests(_RelationTestCase):
    username = 'fam_delete_branch'

    def test_grandchildren_survive_and_lose_the_edge(self):
        grandpa = self.person('Ông', 'male')
        dad = self.person('Cha', 'male', father=grandpa)
        me = self.person('Tôi', father=dad)
        response = self.client.delete(url('family-person-detail', person_id=grandpa.id))
        self.assertEqual(response.json()['detachedFrom'], [str(dad.id)])
        persons = self.client.get(url('family-root')).json()['persons']
        self.assertIsNone(person_by_id(persons, dad.id)['fatherId'])
        self.assertEqual(person_by_id(persons, me.id)['fatherId'], str(dad.id))
