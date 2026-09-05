"""Unit tests for `giapha.services.gio_follow`. No DB -- both functions take
plain edge tuples and dicts, never a queryset, so this runs on
`SimpleTestCase` (same idiom as `test_person_rules.py`).

This is the part of phase 6 that decides who gets a push and who does not, so
it is tested exhaustively here rather than through the command.
"""

from django.test import SimpleTestCase

from giapha.services.gio_follow import ancestors, followers_by_person


class AncestorsTests(SimpleTestCase):
    def test_person_without_parents_has_no_ancestors(self):
        edges = [(1, None, None), (2, 1, None)]
        self.assertEqual(set(), ancestors(edges, 1))

    def test_excludes_the_person_themselves(self):
        edges = [(1, None, None), (2, 1, None)]
        self.assertNotIn(2, ancestors(edges, 2))

    def test_father_line_walks_all_the_way_up(self):
        edges = [(1, None, None), (2, 1, None), (3, 2, None)]
        self.assertEqual({1, 2}, ancestors(edges, 3))

    def test_mother_only_still_resolves(self):
        # Người chỉ khai mẹ: bên ngoại vẫn phải ra tổ tiên.
        edges = [(10, None, None), (11, None, 10), (12, None, 11)]
        self.assertEqual({10, 11}, ancestors(edges, 12))

    def test_both_paternal_and_maternal_lines_are_included(self):
        edges = [
            (1, None, None),   # ông nội
            (2, None, None),   # bà ngoại
            (3, 1, None),      # cha
            (4, None, 2),      # mẹ
            (5, 3, 4),         # người nhận
        ]
        self.assertEqual({1, 2, 3, 4}, ancestors(edges, 5))

    def test_descendants_and_collaterals_are_not_ancestors(self):
        edges = [
            (1, None, None),
            (2, 1, None),      # bản thân
            (3, 1, None),      # anh em (bàng hệ)
            (4, 2, None),      # con
        ]
        self.assertEqual({1}, ancestors(edges, 2))

    def test_ten_generation_chain(self):
        edges = [(1, None, None)] + [(n, n - 1, None) for n in range(2, 11)]
        self.assertEqual(set(range(1, 10)), ancestors(edges, 10))

    def test_cycle_entered_by_hand_terminates_without_raising(self):
        """Django admin bypasses `person_rules.validate_no_cycle`, so a
        1 -> 2 -> 3 -> 1 parent loop can already be in the table. It must
        stop, not hang, and not raise.
        """
        edges = [(1, 3, None), (2, 1, None), (3, 2, None)]
        result = ancestors(edges, 2)
        self.assertEqual({1, 3}, result)  # 2 itself dropped despite the loop

    def test_self_parent_row_is_not_its_own_ancestor(self):
        edges = [(1, 1, None), (2, 1, None)]
        self.assertEqual(set(), ancestors(edges, 1))

    def test_fails_open_with_a_partial_set_when_the_counter_is_exhausted(self):
        """DELIBERATE divergence from `person_rules.descendants`, which
        raises here. A nightly job must not die over one corrupt row.
        """
        edges = [(1, None, None)] + [(n, n - 1, None) for n in range(2, 11)]
        partial = ancestors(edges, 10, max_iterations=2)
        self.assertTrue(partial.issubset({9, 8}))
        self.assertLess(len(partial), 9)


class FollowersByPersonTests(SimpleTestCase):
    # 1 -- ông tổ; 2 -- cha; 3 -- người dùng A; 4 -- chú (bàng hệ); 5 -- người ngoài
    EDGES = [
        (1, None, None),
        (2, 1, None),
        (3, 2, None),
        (4, 1, None),
        (5, None, None),
    ]

    def test_direct_ancestors_are_followed_by_default(self):
        followers = followers_by_person(self.EDGES, {100: 3}, {}, {1, 2, 4})
        self.assertEqual({1: {100}, 2: {100}}, followers)

    def test_person_with_no_follower_is_omitted(self):
        followers = followers_by_person(self.EDGES, {100: 3}, {}, {4})
        self.assertEqual({}, followers)

    def test_member_without_binding_gets_nothing(self):
        followers = followers_by_person(self.EDGES, {}, {}, {1, 2})
        self.assertEqual({}, followers)

    def test_override_enables_a_collateral_relative(self):
        overrides = {(100, 4): True}
        followers = followers_by_person(self.EDGES, {100: 3}, overrides, {1, 2, 4})
        self.assertEqual({1: {100}, 2: {100}, 4: {100}}, followers)

    def test_override_disables_a_direct_ancestor(self):
        overrides = {(100, 1): False}
        followers = followers_by_person(self.EDGES, {100: 3}, overrides, {1, 2})
        self.assertEqual({2: {100}}, followers)

    def test_enabling_override_outside_person_ids_is_ignored(self):
        # Người này không có giỗ đến hạn trong lượt chạy -> override bật vẫn
        # không được kéo vào.
        overrides = {(100, 5): True}
        followers = followers_by_person(self.EDGES, {100: 3}, overrides, {1, 2})
        self.assertEqual({1: {100}, 2: {100}}, followers)

    def test_unbound_member_still_receives_their_manual_follows(self):
        overrides = {(101, 1): True}
        followers = followers_by_person(self.EDGES, {}, overrides, {1, 2})
        self.assertEqual({1: {101}}, followers)

    def test_disabling_override_for_a_non_ancestor_is_a_no_op(self):
        overrides = {(100, 4): False}
        followers = followers_by_person(self.EDGES, {100: 3}, overrides, {1, 2, 4})
        self.assertEqual({1: {100}, 2: {100}}, followers)

    def test_several_users_accumulate_on_the_same_person(self):
        bindings = {100: 3, 101: 4}  # cháu trực hệ và người con thứ của cụ 1
        followers = followers_by_person(self.EDGES, bindings, {}, {1, 2})
        self.assertEqual({1: {100, 101}, 2: {100}}, followers)

    def test_binding_to_a_root_node_yields_no_default_follows(self):
        # Cây thưa: binding vào node chưa khai cha mẹ -> 0 tổ tiên, đúng thiết kế.
        followers = followers_by_person(self.EDGES, {100: 5}, {}, {1, 2, 4})
        self.assertEqual({}, followers)

    def test_cycle_in_the_tree_does_not_break_resolution(self):
        edges = [(1, 3, None), (2, 1, None), (3, 2, None)]
        followers = followers_by_person(edges, {100: 3}, {}, {1, 2, 3})
        self.assertEqual({1: {100}, 2: {100}}, followers)
