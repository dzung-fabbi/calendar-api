"""Query-count ratchet for the `/v1/family` endpoints.

Same mechanism as `test_query_counts.py` (`QueryBudgetMixin`, budgets in
`snapshots/query_budgets.json`), against a 4-person family and a ~400-person
one (spec §1: a real family is < 500). Every endpoint loads the whole tree
with exactly two queries (`selectors.family.load_graph`), so the count must
be identical on both fixtures.

Recorded ceilings (`snapshots/query_budgets.json`), counted inside a
`TestCase` so every `transaction.atomic()` adds a SAVEPOINT/RELEASE pair:
  family_root        3  (Family get_or_create SELECT + persons + spouses)
  family_person      3  (same -- detail is served from the same two queries)
  family_set_parent  8  (family + savepoint pair + load 2 + UPDATE + reload 2)
  family_link_spouse 14 (family + savepoint pairs + load 2 + upsert SELECT/INSERT
                         + touch updated_at + reload 2)
"""

import uuid

from django.test import TestCase
from django.urls import reverse

from giapha.models import FamilyPerson, FamilySpouse
from giapha.tests.family_helpers import client_for, family_of, make_person, make_user
from giapha.tests.test_query_counts import QueryBudgetMixin


def build_large_family(family, generations=8, children_per_couple=2):
    """A balanced tree with a spouse per person of the parent generation --
    ~2^generations persons plus spouses (8 -> ~380). Bulk-inserted."""
    persons, spouses = [], []
    roots = [FamilyPerson(id=uuid.uuid4(), family=family, name='Tổ', gender='male')]
    persons += roots
    current = roots
    for depth in range(1, generations):
        next_level = []
        for parent in current:
            wife = FamilyPerson(id=uuid.uuid4(), family=family, name='Vợ {}'.format(depth), gender='female')
            persons.append(wife)
            spouses.append(FamilySpouse(family=family, person_a_id=min(parent.id, wife.id, key=str),
                                        person_b_id=max(parent.id, wife.id, key=str)))
            for order in range(children_per_couple):
                child = FamilyPerson(
                    id=uuid.uuid4(), family=family, name='Con {}-{}'.format(depth, order),
                    gender='male', father_id=parent.id, mother_id=wife.id, birth_order=order + 1,
                )
                persons.append(child)
                next_level.append(child)
        current = next_level
    FamilyPerson.objects.bulk_create(persons)
    FamilySpouse.objects.bulk_create(spouses)
    return roots[0], current[0]


class FamilyQueryBudgetTests(QueryBudgetMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.small_user = make_user('fam_qc_small')
        small = family_of(cls.small_user)
        cls.small_root = make_person(small, 'Ông', 'male')
        dad = make_person(small, 'Cha', 'male', father=cls.small_root)
        cls.small_leaf = make_person(small, 'Tôi', 'male', father=dad)
        make_person(small, 'Lẻ')

        cls.large_user = make_user('fam_qc_large')
        large = family_of(cls.large_user)
        cls.large_root, cls.large_leaf = build_large_family(large)
        assert FamilyPerson.objects.filter(family=large).count() > 300

    def test_family_root_budget(self):
        small = self.query_count(client_for(self.small_user), reverse('family-root'))
        large = self.query_count(client_for(self.large_user), reverse('family-root'))
        self.assert_budget('family_root', small, large)

    def test_family_person_detail_budget(self):
        small = self.query_count(
            client_for(self.small_user), reverse('family-person-detail', kwargs={'person_id': self.small_leaf.id}),
        )
        large = self.query_count(
            client_for(self.large_user), reverse('family-person-detail', kwargs={'person_id': self.large_leaf.id}),
        )
        self.assert_budget('family_person', small, large)

    def test_family_set_parent_budget(self):
        """Clearing the root's (empty) father slot: a real write path with no
        data-dependent branch, so both fixtures take the same route."""
        body_small = {'childId': str(self.small_root.id), 'slot': 'father', 'parentId': None}
        body_large = {'childId': str(self.large_root.id), 'slot': 'father', 'parentId': None}
        small = self.query_count(
            client_for(self.small_user), reverse('family-set-parent'), method='post', body=body_small,
        )
        large = self.query_count(
            client_for(self.large_user), reverse('family-set-parent'), method='post', body=body_large,
        )
        self.assert_budget('family_set_parent', small, large)

    def test_family_link_spouse_budget(self):
        """Linking a childless leaf to a brand-new person -- no fill side
        effect on either fixture, so the write count is fixed."""
        small_new = make_person(family_of(self.small_user), 'Vợ mới', 'female')
        large_new = make_person(family_of(self.large_user), 'Vợ mới', 'female')
        small = self.query_count(
            client_for(self.small_user), reverse('family-link-spouse'), method='post',
            body={'aId': str(self.small_leaf.id), 'bId': str(small_new.id)},
        )
        large = self.query_count(
            client_for(self.large_user), reverse('family-link-spouse'), method='post',
            body={'aId': str(self.large_leaf.id), 'bId': str(large_new.id)},
        )
        self.assert_budget('family_link_spouse', small, large)
