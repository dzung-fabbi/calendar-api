"""`services.family_scope` -- pure, no database."""

from django.test import SimpleTestCase

from giapha.services.family_scope import branch_scope_ids, family_scope_ids

# Tree (ids):
#   1 ông ── 2 bà            (married)
#   ├── 3 bác (verified)
#   ├── 4 cha ── 5 mẹ        (married)
#   │   ├── 6 ME ── 7 vợ     (married)
#   │   │   └── 8 con ── 9 dâu
#   │   │       └── 10 cháu
#   │   └── 11 em ruột (unverified)
#   └── 12 cô
#   13 anh cùng cha khác mẹ (father 4, mother 14 bà hai)
#   14 bà hai ── married to 4
#   15 con riêng của vợ 7 (mother 7, other father 16)
#   16 chồng trước của 7
EDGES = [
    (1, None, None), (2, None, None), (3, 1, 2), (4, 1, 2), (5, None, None),
    (6, 4, 5), (7, None, None), (8, 6, 7), (9, None, None), (10, 8, 9),
    (11, 4, 5), (12, 1, 2), (13, 4, 14), (14, None, None), (15, 16, 7), (16, None, None),
]
MARRIAGES = [(1, 2), (4, 5), (6, 7), (8, 9), (4, 14), (16, 7)]


class FamilyScopeTests(SimpleTestCase):
    def scope(self, person_id=6, verified=frozenset({3})):
        return family_scope_ids(EDGES, MARRIAGES, person_id, set(verified))

    def test_self_spouse_parents_descendants_and_their_spouses(self):
        scope = self.scope()
        for person_id in (6, 7, 4, 5, 8, 9, 10):
            self.assertIn(person_id, scope)

    def test_unverified_full_and_half_siblings_are_in(self):
        scope = self.scope()
        self.assertIn(11, scope)
        self.assertIn(13, scope)

    def test_verified_sibling_is_out(self):
        self.assertNotIn(11, self.scope(verified={3, 11}))

    def test_grandparents_uncles_and_aunts_are_out(self):
        scope = self.scope()
        for person_id in (1, 2, 3, 12):
            self.assertNotIn(person_id, scope)

    def test_parents_other_spouse_and_spouses_other_family_are_out(self):
        scope = self.scope()
        # bà hai (father's other wife), the wife's child and ex-husband.
        for person_id in (14, 15, 16):
            self.assertNotIn(person_id, scope)

    def test_sibling_rule_does_not_spread_to_their_family(self):
        edges = EDGES + [(17, 11, None)]
        self.assertNotIn(17, family_scope_ids(edges, MARRIAGES, 6, set()))

    def test_unknown_or_deleted_person_has_empty_scope(self):
        self.assertEqual(set(), family_scope_ids(EDGES, MARRIAGES, 999, set()))

    def test_parent_cycle_from_admin_data_terminates(self):
        edges = [(1, 2, None), (2, 1, None)]
        self.assertEqual({1, 2}, family_scope_ids(edges, [], 1, set()))


class BranchScopeTests(SimpleTestCase):
    def test_root_descendants_and_spouses(self):
        self.assertEqual({4, 5, 14, 6, 7, 8, 9, 10, 11, 13}, branch_scope_ids(EDGES, MARRIAGES, 4))

    def test_missing_root_is_empty(self):
        self.assertEqual(set(), branch_scope_ids(EDGES, MARRIAGES, 999))
