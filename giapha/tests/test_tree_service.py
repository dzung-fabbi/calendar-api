"""Unit tests for `giapha.services.tree`. No DB -- every function under test
takes plain edge tuples / `.values()`-shaped dicts, never a queryset or model
instance, so this suite runs on `SimpleTestCase`.
"""

import datetime as dt

from django.test import SimpleTestCase

from giapha.services.tree import (
    NODE_FIELDS,
    compute_generations,
    marriage_edges_from_rows,
    node_from_row,
    parent_edges_from_rows,
    subtree_ids,
)


def _row(person_id, father_id=None, mother_id=None, parent_kind='ruot', **overrides):
    base = {
        'id': person_id, 'ho_ten': 'Người {}'.format(person_id), 'ten_huy': '', 'gioi_tinh': 'nam',
        'generation': None, 'branch': '', 'is_truong': False, 'birth_order': None,
        'birth_solar': None, 'death_solar': None, 'death_lunar_day': None, 'death_lunar_month': None,
        'death_lunar_leap': False, 'father_id': father_id, 'mother_id': mother_id, 'parent_kind': parent_kind,
        'photo_key': '',
    }
    base.update(overrides)
    return base


class ComputeGenerationsTests(SimpleTestCase):
    def test_multiple_disconnected_roots_each_start_at_one(self):
        # A -> B (one component), C -> D (a separate, disconnected component).
        edges = [(1, None, None), (2, 1, None), (3, None, None), (4, 3, None)]
        generations = compute_generations(edges)
        self.assertEqual(1, generations[1])
        self.assertEqual(2, generations[2])
        self.assertEqual(1, generations[3])
        self.assertEqual(2, generations[4])

    def test_child_with_parents_at_different_generations_takes_the_max(self):
        # Father line: 1 -> 2 -> 3 (gen 1, 2, 3). Mother line: 4 (gen 1, no ancestors).
        # Child 5 has father=3 (gen 3) and mother=4 (gen 1) -> max(3, 1) + 1 = 4.
        edges = [
            (1, None, None), (2, 1, None), (3, 2, None),
            (4, None, None),
            (5, 3, 4),
        ]
        generations = compute_generations(edges)
        self.assertEqual(4, generations[5])

    def test_fully_orphaned_person_is_generation_one(self):
        edges = [(1, None, None), (2, None, None)]
        generations = compute_generations(edges)
        self.assertEqual(1, generations[1])
        self.assertEqual(1, generations[2])

    def test_dangling_parent_reference_is_treated_as_unknown(self):
        """`father_id` pointing at an id absent from `edges` (soft-deleted,
        cross-clan, or otherwise corrupt) must not stall the child forever --
        it's treated the same as no known parent.
        """
        edges = [(1, 999, None)]
        generations = compute_generations(edges)
        self.assertEqual(1, generations[1])

    def test_pre_existing_cycle_does_not_hang_and_falls_back_to_one(self):
        """A->B->C->A cycle: none of the three ever reaches pending=0, so the
        safety fallback must assign them a generation instead of leaving the
        walk unresolved (or hanging).
        """
        edges = [(1, 3, None), (2, 1, None), (3, 2, None)]
        generations = compute_generations(edges)
        self.assertEqual({1: 1, 2: 1, 3: 1}, generations)

    def test_cycle_does_not_prevent_unrelated_nodes_from_resolving(self):
        edges = [(1, 3, None), (2, 1, None), (3, 2, None), (10, None, None), (11, 10, None)]
        generations = compute_generations(edges)
        self.assertEqual(1, generations[10])
        self.assertEqual(2, generations[11])

    def test_only_one_parent_known_inherits_from_that_parent(self):
        edges = [(1, None, None), (2, None, None), (3, 1, None)]
        generations = compute_generations(edges)
        self.assertEqual(2, generations[3])


class SubtreeIdsTests(SimpleTestCase):
    def test_includes_root_itself(self):
        edges = [(1, None, None)]
        self.assertEqual({1}, subtree_ids(edges, 1))

    def test_unbounded_depth_returns_every_descendant(self):
        edges = [(1, None, None), (2, 1, None), (3, 2, None)]
        self.assertEqual({1, 2, 3}, subtree_ids(edges, 1))

    def test_depth_one_stops_at_direct_children(self):
        edges = [(1, None, None), (2, 1, None), (3, 2, None)]
        self.assertEqual({1, 2}, subtree_ids(edges, 1, depth=1))

    def test_depth_zero_is_root_only(self):
        edges = [(1, None, None), (2, 1, None)]
        self.assertEqual({1}, subtree_ids(edges, 1, depth=0))

    def test_unrelated_branch_is_excluded(self):
        edges = [(1, None, None), (2, 1, None), (3, None, None), (4, 3, None)]
        self.assertEqual({1, 2}, subtree_ids(edges, 1))

    def test_pre_existing_cycle_does_not_hang(self):
        edges = [(1, 2, None), (2, 1, None)]
        result = subtree_ids(edges, 1)
        self.assertEqual({1, 2}, result)


class NodeFromRowTests(SimpleTestCase):
    def test_living_person_has_no_death_fields(self):
        node = node_from_row(_row(1))
        self.assertTrue(node['is_living'])
        self.assertIsNone(node['death_year'])
        self.assertIsNone(node['death_lunar'])

    def test_solar_death_marks_not_living_and_sets_year(self):
        node = node_from_row(_row(1, death_solar=dt.date(1975, 4, 30)))
        self.assertFalse(node['is_living'])
        self.assertEqual(1975, node['death_year'])

    def test_lunar_only_death_still_marks_not_living(self):
        node = node_from_row(_row(1, death_lunar_day=12, death_lunar_month=8))
        self.assertFalse(node['is_living'])
        self.assertEqual({'day': 12, 'month': 8, 'leap': False}, node['death_lunar'])

    def test_birth_year_derived_from_birth_solar(self):
        node = node_from_row(_row(1, birth_solar=dt.date(1901, 1, 1)))
        self.assertEqual(1901, node['birth_year'])

    def test_node_never_carries_biography_fields(self):
        node = node_from_row(_row(1))
        for leaked_field in ('tieu_su', 'que_quan', 'mo_phan_lat', 'mo_phan_lng'):
            self.assertNotIn(leaked_field, node)

    def test_node_shape_matches_node_fields_contract_for_living_person(self):
        """`TreeNodeSerializer` is a passthrough (no per-field declarations),
        so `NODE_FIELDS` is the only thing left guarding the `/tree` node
        shape. This must hold for both a living and a dead row (`death_lunar`
        and `death_year` are populated differently between the two).
        """
        node = node_from_row(_row(1))
        self.assertEqual(set(NODE_FIELDS), set(node.keys()))

    def test_node_shape_matches_node_fields_contract_for_dead_person(self):
        node = node_from_row(_row(1, death_solar=dt.date(1975, 4, 30)))
        self.assertEqual(set(NODE_FIELDS), set(node.keys()))


class ParentEdgesFromRowsTests(SimpleTestCase):
    def test_both_parents_known_emit_two_role_edges(self):
        rows = [_row(1), _row(2), _row(3, father_id=1, mother_id=2)]
        edges = parent_edges_from_rows(rows)
        roles = {(edge['from'], edge['role']) for edge in edges}
        self.assertEqual({(1, 'father'), (2, 'mother')}, roles)
        self.assertTrue(all(edge['to'] == 3 and edge['type'] == 'parent' for edge in edges))

    def test_parent_outside_given_rows_is_omitted(self):
        # Father (id 1) truncated out / above a `?root=` cut -- only row 2 given.
        rows = [_row(2, father_id=1)]
        self.assertEqual([], parent_edges_from_rows(rows))

    def test_parent_kind_carried_onto_the_edge(self):
        rows = [_row(1), _row(2, father_id=1, parent_kind='nuoi')]
        edges = parent_edges_from_rows(rows)
        self.assertEqual('nuoi', edges[0]['kind'])


class MarriageEdgesFromRowsTests(SimpleTestCase):
    def test_both_partners_included_emits_edge(self):
        rows = [{'husband_id': 1, 'wife_id': 2, 'order': 1, 'status': 'dang_ket_hon'}]
        edges = marriage_edges_from_rows(rows, included_ids={1, 2})
        self.assertEqual(1, len(edges))
        self.assertEqual('marriage', edges[0]['type'])

    def test_partner_outside_included_ids_is_omitted(self):
        rows = [{'husband_id': 1, 'wife_id': 2, 'order': 1, 'status': 'dang_ket_hon'}]
        self.assertEqual([], marriage_edges_from_rows(rows, included_ids={1}))
