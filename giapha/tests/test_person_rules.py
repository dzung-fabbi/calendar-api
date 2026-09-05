"""Unit tests for `giapha.services.person_rules`. No DB -- every function
under test takes plain edge tuples / dicts, never a queryset or model
instance, so this suite runs on `SimpleTestCase`.
"""

import datetime as dt

from django.test import SimpleTestCase

from giapha.services.person_rules import (
    MIN_PARENT_CHILD_GAP_YEARS,
    PersonValidationError,
    descendants,
    ids_from_edges,
    validate_clan_size_cap,
    validate_death_after_birth,
    validate_death_pair_complete,
    validate_lunar_death_valid,
    validate_marriage_distinct,
    validate_marriage_order_unique,
    validate_no_cycle,
    validate_parent_born_before_child,
    validate_parent_in_same_clan,
    validate_person_write,
    validate_self_not_parent,
)


class DescendantsTests(SimpleTestCase):
    def test_direct_child_is_a_descendant(self):
        edges = [(1, None, None), (2, 1, None)]
        self.assertEqual({2}, descendants(edges, 1))

    def test_indirect_grandchild_is_a_descendant(self):
        # 1 -> 2 -> 3 -> 4 (father chain)
        edges = [(1, None, None), (2, 1, None), (3, 2, None), (4, 3, None)]
        self.assertEqual({2, 3, 4}, descendants(edges, 1))

    def test_unrelated_person_is_not_a_descendant(self):
        edges = [(1, None, None), (2, None, None)]
        self.assertEqual(set(), descendants(edges, 1))

    def test_mother_edge_also_counts(self):
        edges = [(1, None, None), (2, None, 1)]
        self.assertEqual({2}, descendants(edges, 1))

    def test_pre_existing_cycle_does_not_hang_and_returns(self):
        """Data entered through Django admin bypasses this module entirely,
        so a pre-existing A->B->C->A cycle must not make the BFS spin
        forever -- the safety counter must bound it.
        """
        edges = [(1, 3, None), (2, 1, None), (3, 2, None)]  # 1<-3<-2<-1
        result = descendants(edges, 1)
        self.assertIsInstance(result, set)
        self.assertEqual({1, 2, 3}, result)

    def test_self_referencing_row_does_not_hang(self):
        edges = [(1, 1, None), (2, 1, None)]
        result = descendants(edges, 1)
        self.assertEqual({1, 2}, result)

    def test_exhausted_safety_cap_fails_closed_not_open(self):
        """The cap never actually fires under real inputs (termination comes
        from the `visited` set -- each id is enqueued at most once, so
        iterations <= N, always below the `2N+10` default cap). But IF it
        ever did, returning a PARTIAL descendant set would let
        `validate_no_cycle` wave a real cycle through -- worse than no
        safety net at all. `max_iterations` is overridable so this can be
        proven deterministically instead of relying on a graph large enough
        to hit the real cap.
        """
        edges = [(1, None, None), (2, 1, None)]
        with self.assertRaises(PersonValidationError):
            descendants(edges, 1, max_iterations=0)


class ValidateNoCycleTests(SimpleTestCase):
    def test_assigning_an_unrelated_parent_is_valid(self):
        edges = [(1, None, None), (2, None, None)]
        validate_no_cycle(edges, person_id=2, father_id=1, mother_id=None)  # no raise

    def test_new_person_never_raises(self):
        edges = [(1, None, None)]
        validate_no_cycle(edges, person_id=None, father_id=1, mother_id=None)  # no raise

    def test_direct_cycle_is_rejected(self):
        # 2's father is 1 -> assigning 1's father to 2 would close a 2-node cycle.
        edges = [(1, None, None), (2, 1, None)]
        with self.assertRaises(PersonValidationError):
            validate_no_cycle(edges, person_id=1, father_id=2, mother_id=None)

    def test_indirect_cycle_through_three_generations_is_rejected(self):
        # A(1) -> B(2) -> C(3) father chain; assigning C as A's father closes it.
        edges = [(1, None, None), (2, 1, None), (3, 2, None)]
        with self.assertRaises(PersonValidationError):
            validate_no_cycle(edges, person_id=1, father_id=3, mother_id=None)

    def test_indirect_cycle_via_mother_is_also_rejected(self):
        edges = [(1, None, None), (2, None, 1), (3, None, 2)]
        with self.assertRaises(PersonValidationError):
            validate_no_cycle(edges, person_id=1, mother_id=3, father_id=None)


class ValidateParentInSameClanTests(SimpleTestCase):
    def test_parent_present_in_clan_is_valid(self):
        validate_parent_in_same_clan({1, 2}, father_id=1, mother_id=2)  # no raise

    def test_none_parents_are_valid(self):
        validate_parent_in_same_clan({1, 2}, father_id=None, mother_id=None)  # no raise

    def test_father_from_another_clan_is_rejected(self):
        with self.assertRaises(PersonValidationError):
            validate_parent_in_same_clan({1, 2}, father_id=999, mother_id=None)

    def test_mother_from_another_clan_is_rejected(self):
        with self.assertRaises(PersonValidationError):
            validate_parent_in_same_clan({1, 2}, father_id=None, mother_id=999)


class ValidateSelfNotParentTests(SimpleTestCase):
    def test_different_ids_are_valid(self):
        validate_self_not_parent(1, father_id=2, mother_id=3)  # no raise

    def test_new_person_is_valid(self):
        validate_self_not_parent(None, father_id=1, mother_id=2)  # no raise

    def test_self_as_father_is_rejected(self):
        with self.assertRaises(PersonValidationError):
            validate_self_not_parent(1, father_id=1, mother_id=None)

    def test_self_as_mother_is_rejected(self):
        with self.assertRaises(PersonValidationError):
            validate_self_not_parent(1, father_id=None, mother_id=1)


class ValidateParentBornBeforeChildTests(SimpleTestCase):
    def test_gap_of_exactly_minimum_years_is_valid(self):
        father_birth = dt.date(1980, 1, 1)
        child_birth = dt.date(1980 + MIN_PARENT_CHILD_GAP_YEARS, 1, 1)
        validate_parent_born_before_child(child_birth, father_birth, None)  # no raise

    def test_unknown_birth_dates_are_valid(self):
        validate_parent_born_before_child(None, None, None)  # no raise

    def test_gap_under_minimum_is_rejected(self):
        father_birth = dt.date(1980, 1, 1)
        child_birth = dt.date(1990, 1, 1)  # 10 years, under the 12-year floor
        with self.assertRaises(PersonValidationError):
            validate_parent_born_before_child(child_birth, father_birth, None)

    def test_child_born_before_parent_is_rejected(self):
        father_birth = dt.date(1990, 1, 1)
        child_birth = dt.date(1980, 1, 1)
        with self.assertRaises(PersonValidationError):
            validate_parent_born_before_child(child_birth, father_birth, None)

    def test_force_bypasses_the_check(self):
        father_birth = dt.date(1980, 1, 1)
        child_birth = dt.date(1985, 1, 1)
        validate_parent_born_before_child(child_birth, father_birth, None, force=True)  # no raise


class ValidateDeathAfterBirthTests(SimpleTestCase):
    def test_death_after_birth_is_valid(self):
        validate_death_after_birth(dt.date(2000, 1, 1), dt.date(2020, 1, 1))  # no raise

    def test_death_same_day_as_birth_is_valid(self):
        validate_death_after_birth(dt.date(2000, 1, 1), dt.date(2000, 1, 1))  # no raise

    def test_unknown_dates_are_valid(self):
        validate_death_after_birth(None, None)  # no raise

    def test_death_before_birth_is_rejected(self):
        with self.assertRaises(PersonValidationError):
            validate_death_after_birth(dt.date(2000, 1, 1), dt.date(1999, 1, 1))


class ValidateLunarDeathValidTests(SimpleTestCase):
    def test_in_range_values_are_valid(self):
        validate_lunar_death_valid(12, 30)  # no raise

    def test_none_values_are_valid(self):
        validate_lunar_death_valid(None, None)  # no raise

    def test_month_out_of_range_is_rejected(self):
        with self.assertRaises(PersonValidationError):
            validate_lunar_death_valid(13, 15)

    def test_day_out_of_range_is_rejected(self):
        with self.assertRaises(PersonValidationError):
            validate_lunar_death_valid(6, 31)


class ValidateDeathPairCompleteTests(SimpleTestCase):
    def test_both_present_is_valid(self):
        validate_death_pair_complete(10, 5)  # no raise

    def test_both_absent_is_valid(self):
        validate_death_pair_complete(None, None)  # no raise

    def test_day_without_month_is_rejected(self):
        with self.assertRaises(PersonValidationError):
            validate_death_pair_complete(10, None)

    def test_month_without_day_is_rejected(self):
        with self.assertRaises(PersonValidationError):
            validate_death_pair_complete(None, 5)


class ValidateClanSizeCapTests(SimpleTestCase):
    def test_under_cap_is_valid(self):
        validate_clan_size_cap(current_count=10, max_persons=5000)  # no raise

    def test_at_cap_is_rejected(self):
        with self.assertRaises(PersonValidationError):
            validate_clan_size_cap(current_count=5000, max_persons=5000)

    def test_over_cap_is_rejected(self):
        with self.assertRaises(PersonValidationError):
            validate_clan_size_cap(current_count=5001, max_persons=5000)


class ValidateMarriageDistinctTests(SimpleTestCase):
    def test_different_people_is_valid(self):
        validate_marriage_distinct(1, 2)  # no raise

    def test_same_person_is_rejected(self):
        with self.assertRaises(PersonValidationError):
            validate_marriage_distinct(1, 1)


class ValidateMarriageOrderUniqueTests(SimpleTestCase):
    def test_unused_order_is_valid(self):
        validate_marriage_order_unique([(10, 1)], order=2)  # no raise

    def test_duplicate_order_is_rejected(self):
        with self.assertRaises(PersonValidationError):
            validate_marriage_order_unique([(10, 1), (11, 2)], order=2)

    def test_excluding_own_marriage_id_allows_keeping_its_order(self):
        validate_marriage_order_unique([(10, 1)], order=1, exclude_marriage_id=10)  # no raise


class IdsFromEdgesTests(SimpleTestCase):
    def test_returns_every_id_in_edges(self):
        edges = [(1, None, None), (2, 1, None), (3, None, 1)]
        self.assertEqual({1, 2, 3}, ids_from_edges(edges))


class ValidatePersonWriteTests(SimpleTestCase):
    """Smoke tests for the orchestrator that the views call directly."""

    def test_valid_new_person_passes(self):
        validate_person_write(
            {'father_id': 1, 'mother_id': None, 'birth_solar': None, 'death_solar': None,
             'death_lunar_day': None, 'death_lunar_month': None},
            edges=[(1, None, None)], ids_in_clan={1}, birth_map={1: None},
            existing_count=1, max_persons=5000, person_id=None,
        )  # no raise

    def test_cap_reached_blocks_new_person(self):
        with self.assertRaises(PersonValidationError):
            validate_person_write(
                {'father_id': None, 'mother_id': None, 'birth_solar': None, 'death_solar': None,
                 'death_lunar_day': None, 'death_lunar_month': None},
                edges=[], ids_in_clan=set(), birth_map={},
                existing_count=5000, max_persons=5000, person_id=None,
            )

    def test_update_skips_the_cap_check(self):
        # existing_count already "over" the cap, but this is an update (person_id set) -> no raise.
        validate_person_write(
            {'father_id': None, 'mother_id': None, 'birth_solar': None, 'death_solar': None,
             'death_lunar_day': None, 'death_lunar_month': None},
            edges=[(7, None, None)], ids_in_clan={7}, birth_map={7: None},
            existing_count=99999, max_persons=5000, person_id=7,
        )  # no raise

    def test_update_still_rejects_a_cycle(self):
        edges = [(1, None, None), (2, 1, None)]
        with self.assertRaises(PersonValidationError):
            validate_person_write(
                {'father_id': 2, 'mother_id': None, 'birth_solar': None, 'death_solar': None,
                 'death_lunar_day': None, 'death_lunar_month': None},
                edges=edges, ids_in_clan={1, 2}, birth_map={1: None, 2: None},
                existing_count=2, max_persons=5000, person_id=1,
            )
