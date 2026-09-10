"""Pure-rule coverage for the personal family API: graph derivations, the
spec §4 invariants, label planning and date derivation. `SimpleTestCase`, no
database -- everything here takes plain dicts.
"""

import datetime as dt
import uuid

from django.test import SimpleTestCase

from giapha.services import family_rules as rules
from giapha.services.family_dates import derive_solar_death, has_lunar_death
from giapha.services.family_graph import FamilyGraph, canonical_pair, gender_fits_slot, slot_for_parent_gender
from giapha.services.family_issue import FamilyRuleError
from giapha.services.family_labels import plan_link


def row(pid, gender='unknown', father=None, mother=None):
    return {'id': pid, 'gender': gender, 'father_id': father, 'mother_id': mother}


def spouse(a, b, kind='married'):
    return {'person_a_id': a, 'person_b_id': b, 'type': kind}


class SlotHelperTests(SimpleTestCase):
    def test_female_goes_to_mother_everyone_else_to_father(self):
        self.assertEqual(slot_for_parent_gender('female'), 'mother')
        self.assertEqual(slot_for_parent_gender('male'), 'father')
        self.assertEqual(slot_for_parent_gender('unknown'), 'father')

    def test_unknown_fits_both_slots(self):
        self.assertTrue(gender_fits_slot('unknown', 'father'))
        self.assertTrue(gender_fits_slot('unknown', 'mother'))
        self.assertFalse(gender_fits_slot('female', 'father'))
        self.assertFalse(gender_fits_slot('male', 'mother'))

    def test_canonical_pair_is_order_independent(self):
        a, b = uuid.uuid4(), uuid.uuid4()
        self.assertEqual(canonical_pair(a, b), canonical_pair(b, a))


class GraphDerivationTests(SimpleTestCase):
    def setUp(self):
        # grandpa -> father -> me ; mother is co-parent of me (not married to father)
        self.grandpa, self.father, self.mother, self.me, self.wife = (uuid.uuid4() for _ in range(5))
        self.graph = FamilyGraph(
            [
                row(self.grandpa, 'male'),
                row(self.father, 'male', father=self.grandpa),
                row(self.mother, 'female'),
                row(self.me, 'male', father=self.father, mother=self.mother),
                row(self.wife, 'female'),
            ],
            [spouse(self.me, self.wife)],
        )

    def test_children_and_ancestors_are_derived_from_upward_edges(self):
        self.assertEqual(self.graph.children_of(self.father), [self.me])
        self.assertEqual(self.graph.ancestors_of(self.me), {self.father, self.mother, self.grandpa})
        self.assertEqual(self.graph.descendants_of(self.grandpa), {self.father, self.me})

    def test_partners_are_spouses_plus_co_parents(self):
        self.assertEqual(self.graph.co_parents_of(self.father), {self.mother})
        self.assertEqual(self.graph.partners_of(self.father), {self.mother})
        self.assertEqual(self.graph.partners_of(self.me), {self.wife})
        self.assertEqual(self.graph.spouses_of(self.me), {self.wife: 'married'})

    def test_is_lineal(self):
        self.assertTrue(self.graph.is_lineal(self.grandpa, self.me))
        self.assertFalse(self.graph.is_lineal(self.me, self.wife))

    def test_ancestor_walk_terminates_on_corrupt_cycle(self):
        a, b = uuid.uuid4(), uuid.uuid4()
        graph = FamilyGraph([row(a, father=b), row(b, father=a)])
        self.assertEqual(graph.ancestors_of(a), {a, b})


class SetParentRuleTests(SimpleTestCase):
    def setUp(self):
        self.grandpa, self.father, self.me = (uuid.uuid4() for _ in range(3))
        self.graph = FamilyGraph([
            row(self.grandpa, 'male'),
            row(self.father, 'male', father=self.grandpa),
            row(self.me, 'male', father=self.father),
        ])

    def assertCode(self, code, fn, *args):
        with self.assertRaises(FamilyRuleError) as ctx:
            fn(*args)
        self.assertEqual(ctx.exception.code, code)
        return ctx.exception

    def test_self_parent(self):
        self.assertCode('SELF_PARENT', rules.check_set_parent, self.graph, self.me, 'father', self.me)

    def test_dangling_parent_names_the_slot(self):
        self.assertCode('DANGLING_MOTHER', rules.check_set_parent, self.graph, self.me, 'mother', uuid.uuid4())

    def test_gender_mismatch(self):
        woman = uuid.uuid4()
        self.graph.add_person(row(woman, 'female'))
        self.assertCode('GENDER_MISMATCH', rules.check_set_parent, self.graph, self.me, 'father', woman)

    def test_grandchild_as_father_of_grandfather_is_a_cycle(self):
        exc = self.assertCode('PARENT_CYCLE', rules.check_set_parent, self.graph, self.grandpa, 'father', self.me)
        self.assertEqual(exc.person_id, self.grandpa)
        self.assertEqual(exc.other_id, self.me)
        self.assertIn('vòng lặp', exc.message)

    def test_slot_taken_only_for_a_different_person(self):
        rules.check_slot_free(self.graph, self.me, 'father', self.father)  # same person: fine
        rules.check_slot_free(self.graph, self.me, 'mother', self.grandpa)  # empty slot: fine
        exc = self.assertCode('PARENT_SLOT_TAKEN', rules.check_slot_free, self.graph, self.me, 'father', self.grandpa)
        self.assertIn('Cha dượng', exc.message)


class SpouseRuleTests(SimpleTestCase):
    def setUp(self):
        self.father, self.me, self.wife, self.kid = (uuid.uuid4() for _ in range(4))
        self.graph = FamilyGraph([
            row(self.father, 'male'),
            row(self.me, 'male', father=self.father),
            row(self.wife, 'female'),
            row(self.kid, 'unknown', father=self.me),
        ])

    def test_self_spouse_and_dangling(self):
        with self.assertRaises(FamilyRuleError) as ctx:
            rules.check_link_spouse(self.graph, self.me, self.me)
        self.assertEqual(ctx.exception.code, 'SELF_SPOUSE')
        with self.assertRaises(FamilyRuleError) as ctx:
            rules.check_link_spouse(self.graph, self.me, uuid.uuid4())
        self.assertEqual(ctx.exception.code, 'DANGLING_SPOUSE')

    def test_lineal_spouse_is_a_warning_not_an_error(self):
        warning = rules.check_link_spouse(self.graph, self.me, self.father)
        self.assertEqual(warning['code'], 'SPOUSE_IS_ANCESTOR')
        self.assertIsNone(rules.check_link_spouse(self.graph, self.me, self.wife))

    def test_first_spouse_fills_empty_mother_slot_of_existing_children(self):
        self.assertEqual(rules.first_spouse_fill_targets(self.graph, self.me, self.wife), [(self.kid, 'mother')])

    def test_second_spouse_never_fills(self):
        first = uuid.uuid4()
        self.graph.add_person(row(first, 'female'))
        self.graph.add_spouse(self.me, first)
        self.assertEqual(rules.first_spouse_fill_targets(self.graph, self.me, self.wife), [])

    def test_fill_skips_when_gender_does_not_fit(self):
        man = uuid.uuid4()
        self.graph.add_person(row(man, 'male'))
        self.assertEqual(rules.first_spouse_fill_targets(self.graph, self.me, man), [])

    def test_fill_skips_when_slot_is_already_taken(self):
        self.graph.set_parent(self.kid, 'mother', self.wife)
        other = uuid.uuid4()
        self.graph.add_person(row(other, 'female'))
        self.assertEqual(rules.first_spouse_fill_targets(self.graph, self.me, other), [])


class OtherParentCandidateTests(SimpleTestCase):
    def setUp(self):
        self.dad, self.wife1, self.wife2, self.child = (uuid.uuid4() for _ in range(4))
        self.graph = FamilyGraph(
            [row(self.dad, 'male'), row(self.wife1, 'female'), row(self.wife2, 'female'), row(self.child)],
            [spouse(self.dad, self.wife1), spouse(self.dad, self.wife2)],
        )

    def test_two_candidates_means_nobody_is_guessed(self):
        candidates = rules.other_parent_candidates(self.graph, self.dad, self.child, 'mother')
        self.assertEqual(set(candidates), {self.wife1, self.wife2})
        self.assertIsNone(rules.pick_other_parent(candidates, None))
        self.assertEqual(rules.pick_other_parent(candidates, self.wife2), self.wife2)
        self.assertIsNone(rules.pick_other_parent(candidates, uuid.uuid4()))

    def test_single_candidate_is_picked_and_co_parents_count(self):
        graph = FamilyGraph([
            row(self.dad, 'male'), row(self.wife1, 'female'),
            row(self.child, father=self.dad, mother=self.wife1), row(uuid.uuid4()),
        ])
        new_child = uuid.uuid4()
        graph.add_person(row(new_child, father=self.dad))
        candidates = rules.other_parent_candidates(graph, self.dad, new_child, 'mother')
        self.assertEqual(rules.pick_other_parent(candidates, None), self.wife1)


class AddRelativeGateTests(SimpleTestCase):
    def setUp(self):
        self.father, self.me, self.orphan = (uuid.uuid4() for _ in range(3))
        self.graph = FamilyGraph([row(self.father, 'male'), row(self.me, father=self.father), row(self.orphan)])

    def test_second_father_is_rejected_before_creation(self):
        with self.assertRaises(FamilyRuleError) as ctx:
            rules.check_add_relative(self.graph, self.me, 'father', 'male')
        self.assertEqual(ctx.exception.code, 'PARENT_SLOT_TAKEN')

    def test_sibling_without_any_parent_is_rejected(self):
        with self.assertRaises(FamilyRuleError) as ctx:
            rules.check_add_relative(self.graph, self.orphan, 'sibling', 'unknown')
        self.assertEqual(ctx.exception.code, 'NO_PARENT_FOR_SIBLING')
        rules.check_add_relative(self.graph, self.me, 'sibling', 'unknown')  # one parent is enough

    def test_female_cannot_be_added_as_father(self):
        with self.assertRaises(FamilyRuleError) as ctx:
            rules.check_add_relative(self.graph, self.orphan, 'father', 'female')
        self.assertEqual(ctx.exception.code, 'GENDER_MISMATCH')

    def test_unknown_anchor_is_404(self):
        with self.assertRaises(FamilyRuleError) as ctx:
            rules.check_add_relative(self.graph, uuid.uuid4(), 'spouse', 'unknown')
        self.assertEqual(ctx.exception.status, 404)


class LabelPlanTests(SimpleTestCase):
    def setUp(self):
        self.me, self.father, self.new = (uuid.uuid4() for _ in range(3))
        self.graph = FamilyGraph([row(self.father, 'male'), row(self.me, 'male', father=self.father), row(self.new)])

    def test_direct_edges(self):
        self.assertEqual(plan_link(self.graph, self.me, 'Mẹ', 'female'), (('set_parent', self.me, 'mother'), None))
        self.assertEqual(plan_link(self.graph, self.me, 'Vợ', 'female'), (('spouse',), None))
        self.assertEqual(plan_link(self.graph, self.me, 'Con', 'unknown'), (('child',), None))
        self.assertEqual(plan_link(self.graph, self.me, 'Em', 'unknown'), (('sibling',), None))

    def test_grandparent_goes_through_existing_parent(self):
        plan, hint = plan_link(self.graph, self.me, 'Ông nội', 'male')
        self.assertEqual(plan, ('set_parent', self.father, 'father'))
        plan, hint = plan_link(self.graph, self.me, 'Bà ngoại', 'female')
        self.assertIsNone(plan)
        self.assertIn('Chưa có Mẹ', hint)

    def test_taken_slot_gives_hint_not_plan(self):
        plan, hint = plan_link(self.graph, self.me, 'Cha', 'male')
        self.assertIsNone(plan)
        self.assertIn('đã khai Cha', hint)

    def test_ambiguous_or_free_text_labels_are_not_linked_and_have_no_hint(self):
        for label in ('Cụ / Tổ tiên', 'Cháu', 'Chắt', 'Hậu duệ', 'Bác họ', '', None):
            self.assertEqual(plan_link(self.graph, self.me, label, 'unknown'), (None, None))

    def test_no_self_yields_hint_for_linkable_labels_only(self):
        _, hint = plan_link(self.graph, None, 'Cha', 'male')
        self.assertIn('Đây là tôi', hint)
        self.assertEqual(plan_link(self.graph, None, 'Cháu', 'male'), (None, None))


class DateDerivationTests(SimpleTestCase):
    def test_has_lunar_death_needs_day_and_month_only(self):
        self.assertTrue(has_lunar_death(20, 12))
        self.assertFalse(has_lunar_death(0, 12))
        self.assertFalse(has_lunar_death(15, 13))
        self.assertFalse(has_lunar_death(None, 3))

    def test_solar_death_is_derived_only_from_a_complete_lunar_date(self):
        # Mùng 1 Tết Giáp Thìn = 10/02/2024.
        self.assertEqual(derive_solar_death(1, 1, 2024, False), dt.date(2024, 2, 10))
        self.assertIsNone(derive_solar_death(1, 1, None, False))
        self.assertIsNone(derive_solar_death(1, 1, 1500, False))

    def test_wrong_leap_flag_falls_back_to_regular_month(self):
        # 2024 has no leap month 1; the flag must not block the write.
        self.assertEqual(derive_solar_death(1, 1, 2024, True), dt.date(2024, 2, 10))
