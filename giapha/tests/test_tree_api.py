"""API-level tests for `GET /tree`, the `?q=&generation=&branch=&death_year=`
person search/filter, and the PATCH-triggered descendant generation recompute.
Pure-function coverage (generation algorithm edge cases, subtree BFS, row
shaping) lives in `test_tree_service.py`.
"""

import datetime as dt

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.models import Marriage, Person
from giapha.tests.factories import build_clan_fixture, build_person


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def tree_url(clan_id, **query):
    url = reverse('clan-tree', kwargs={'clan_id': clan_id})
    if query:
        url += '?' + '&'.join('{}={}'.format(k, v) for k, v in query.items())
    return url


def persons_url(clan_id, **query):
    url = reverse('person-list-create', kwargs={'clan_id': clan_id})
    if query:
        url += '?' + '&'.join('{}={}'.format(k, v) for k, v in query.items())
    return url


def person_url(clan_id, person_id):
    return reverse('person-detail', kwargs={'clan_id': clan_id, 'person_id': person_id})


class TreeQueryBudgetTests(TestCase):
    """`GET /tree` must cost the same number of queries no matter how many
    persons or marriages the clan has.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']

        cls.grandparent = build_person(cls.clan, ho_ten='Cụ')
        cls.parent = build_person(cls.clan, ho_ten='Ông', father=cls.grandparent)
        cls.child = build_person(cls.clan, ho_ten='Cháu', father=cls.parent)
        cls.spouse = build_person(cls.clan, ho_ten='Vợ ông', gioi_tinh='nu')
        Marriage.objects.create(husband=cls.parent, wife=cls.spouse, status='dang_ket_hon')

    def test_costs_at_most_three_queries(self):
        client = client_for(self.fixture['viewer'])
        with self.assertNumQueries(3):
            response = client.get(tree_url(self.clan.id))
        self.assertEqual(200, response.status_code)

    def test_query_count_does_not_grow_with_more_persons(self):
        for i in range(20):
            build_person(self.clan, ho_ten='Thêm {}'.format(i), father=self.grandparent)

        client = client_for(self.fixture['viewer'])
        with self.assertNumQueries(3):
            response = client.get(tree_url(self.clan.id))
        self.assertEqual(200, response.status_code)

    def test_root_and_depth_do_not_add_a_query(self):
        client = client_for(self.fixture['viewer'])
        with self.assertNumQueries(3):
            response = client.get(tree_url(self.clan.id, root=self.grandparent.id, depth=1))
        self.assertEqual(200, response.status_code)


class TreeShapeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']

    def test_response_has_clan_nodes_edges_truncated(self):
        build_person(self.clan)
        body = client_for(self.fixture['viewer']).get(tree_url(self.clan.id)).json()
        self.assertEqual(self.clan.id, body['clan']['id'])
        self.assertEqual(self.clan.ten_ho, body['clan']['ten_ho'])
        self.assertIn('nodes', body)
        self.assertIn('edges', body)
        self.assertFalse(body['truncated'])

    def test_empty_clan_still_returns_clan_name(self):
        body = client_for(self.fixture['viewer']).get(tree_url(self.clan.id)).json()
        self.assertEqual(self.clan.ten_ho, body['clan']['ten_ho'])
        self.assertEqual([], body['nodes'])
        self.assertEqual([], body['edges'])

    def test_node_shape_is_lean_and_has_no_biography_fields(self):
        build_person(self.clan, ho_ten='A', ten_huy='Huý A', branch='Chi 1', is_truong=True)
        node = client_for(self.fixture['viewer']).get(tree_url(self.clan.id)).json()['nodes'][0]
        for field in ('id', 'ho_ten', 'ten_huy', 'gioi_tinh', 'generation', 'branch',
                      'is_truong', 'birth_order', 'is_living', 'birth_year', 'death_year',
                      'death_lunar', 'photo_url'):
            self.assertIn(field, node)
        for leaked in ('tieu_su', 'que_quan', 'mo_phan_lat', 'mo_phan_lng', 'x', 'y'):
            self.assertNotIn(leaked, node)

    def test_parent_and_marriage_edges_are_both_present(self):
        father = build_person(self.clan, ho_ten='Cha')
        mother = build_person(self.clan, ho_ten='Mẹ', gioi_tinh='nu')
        build_person(self.clan, ho_ten='Con', father=father, mother=mother)
        Marriage.objects.create(husband=father, wife=mother, status='dang_ket_hon')

        edges = client_for(self.fixture['viewer']).get(tree_url(self.clan.id)).json()['edges']
        types = {edge['type'] for edge in edges}
        self.assertEqual({'parent', 'marriage'}, types)
        roles = {edge['role'] for edge in edges if edge['type'] == 'parent'}
        self.assertEqual({'father', 'mother'}, roles)

    def test_soft_deleted_person_absent_from_nodes_and_edges(self):
        parent = build_person(self.clan, ho_ten='Còn')
        deleted_child = build_person(self.clan, ho_ten='Đã xoá', father=parent)
        deleted_child.is_deleted = True
        deleted_child.save(update_fields=['is_deleted'])

        body = client_for(self.fixture['viewer']).get(tree_url(self.clan.id)).json()
        node_ids = {node['id'] for node in body['nodes']}
        self.assertNotIn(deleted_child.id, node_ids)
        edge_targets = {edge.get('to') for edge in body['edges'] if edge['type'] == 'parent'}
        self.assertNotIn(deleted_child.id, edge_targets)

    def test_outsider_gets_404(self):
        build_person(self.clan)
        response = client_for(self.fixture['outsider']).get(tree_url(self.clan.id))
        self.assertEqual(404, response.status_code)


class TreeRootDepthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']
        cls.root = build_person(cls.clan, ho_ten='Gốc')
        cls.child = build_person(cls.clan, ho_ten='Con', father=cls.root)
        cls.grandchild = build_person(cls.clan, ho_ten='Cháu', father=cls.child)
        cls.unrelated = build_person(cls.clan, ho_ten='Không liên quan')

    def test_root_restricts_to_subtree_including_root(self):
        body = client_for(self.fixture['viewer']).get(tree_url(self.clan.id, root=self.root.id)).json()
        ids = {node['id'] for node in body['nodes']}
        self.assertEqual({self.root.id, self.child.id, self.grandchild.id}, ids)

    def test_depth_limits_levels(self):
        body = client_for(self.fixture['viewer']).get(
            tree_url(self.clan.id, root=self.root.id, depth=1)
        ).json()
        ids = {node['id'] for node in body['nodes']}
        self.assertEqual({self.root.id, self.child.id}, ids)

    def test_unknown_root_is_404(self):
        response = client_for(self.fixture['viewer']).get(tree_url(self.clan.id, root=999999))
        self.assertEqual(404, response.status_code)

    def test_non_integer_root_is_400(self):
        response = client_for(self.fixture['viewer']).get(tree_url(self.clan.id, root='abc'))
        self.assertEqual(400, response.status_code)


class TreeTruncationTests(TestCase):
    @override_settings(MAX_CLAN_PERSONS=2)
    def test_truncated_flag_and_size_at_the_cap(self):
        fixture = build_clan_fixture(suffix='_trunc')
        for i in range(3):
            build_person(fixture['clan'], ho_ten='Người {}'.format(i))

        body = client_for(fixture['viewer']).get(tree_url(fixture['clan'].id)).json()
        self.assertTrue(body['truncated'])
        self.assertEqual(2, len(body['nodes']))


class PersonSearchAndFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_search')
        cls.clan = cls.fixture['clan']

    def test_q_matches_ho_ten(self):
        build_person(self.clan, ho_ten='Nguyễn Văn A')
        build_person(self.clan, ho_ten='Trần Thị B')
        body = client_for(self.fixture['viewer']).get(persons_url(self.clan.id, q='Nguyễn')).json()
        names = {row['ho_ten'] for row in body['data']}
        self.assertEqual({'Nguyễn Văn A'}, names)

    def test_q_matches_ten_huy_too(self):
        build_person(self.clan, ho_ten='Người X', ten_huy='HuyRieng')
        build_person(self.clan, ho_ten='Người Y', ten_huy='Khác')
        body = client_for(self.fixture['viewer']).get(persons_url(self.clan.id, q='HuyRieng')).json()
        ids = [row['id'] for row in body['data']]
        self.assertEqual(1, len(ids))

    def test_generation_filter(self):
        build_person(self.clan, ho_ten='Đời 1', generation=1)
        build_person(self.clan, ho_ten='Đời 2', generation=2)
        body = client_for(self.fixture['viewer']).get(persons_url(self.clan.id, generation=2)).json()
        self.assertEqual(1, len(body['data']))
        self.assertEqual('Đời 2', body['data'][0]['ho_ten'])

    def test_branch_filter(self):
        build_person(self.clan, ho_ten='Chi 1', branch='Chi 1')
        build_person(self.clan, ho_ten='Chi 2', branch='Chi 2')
        body = client_for(self.fixture['viewer']).get(persons_url(self.clan.id, branch='Chi 2')).json()
        self.assertEqual(1, len(body['data']))
        self.assertEqual('Chi 2', body['data'][0]['ho_ten'])

    def test_death_year_filter(self):
        build_person(self.clan, ho_ten='Mất 1975', death_solar=dt.date(1975, 4, 30))
        build_person(self.clan, ho_ten='Mất 1990', death_solar=dt.date(1990, 1, 1))
        body = client_for(self.fixture['viewer']).get(persons_url(self.clan.id, death_year=1975)).json()
        self.assertEqual(1, len(body['data']))
        self.assertEqual('Mất 1975', body['data'][0]['ho_ten'])

    def test_invalid_generation_is_400(self):
        response = client_for(self.fixture['viewer']).get(persons_url(self.clan.id, generation='abc'))
        self.assertEqual(400, response.status_code)

    def test_list_still_uses_limit_offset_pagination(self):
        for i in range(3):
            build_person(self.clan, ho_ten='Người {}'.format(i))
        body = client_for(self.fixture['viewer']).get(persons_url(self.clan.id)).json()
        self.assertIn('count', body)
        self.assertIn('next', body)
        self.assertGreaterEqual(body['count'], 3)


class RecomputeOnParentChangeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_recompute')
        cls.clan = cls.fixture['clan']

    def test_changing_father_recomputes_descendant_subtree(self):
        # Two independent root chains: root_a(gen1) -> mid_a(gen2), and
        # root_b(gen1) alone. Moving mid_a under root_b should not change
        # mid_a's generation (still 2), but the grandchild below it must
        # follow along.
        root_a = build_person(self.clan, ho_ten='Gốc A', generation=1)
        mid_a = build_person(self.clan, ho_ten='Giữa A', father=root_a, generation=2)
        grandchild = build_person(self.clan, ho_ten='Cháu A', father=mid_a, generation=3)
        root_b = build_person(self.clan, ho_ten='Gốc B', generation=1)

        response = client_for(self.fixture['editor']).patch(
            person_url(self.clan.id, mid_a.id), {'father_id': root_b.id}, format='json',
        )
        self.assertEqual(200, response.status_code)

        grandchild.refresh_from_db()
        mid_a.refresh_from_db()
        self.assertEqual(2, mid_a.generation)
        self.assertEqual(3, grandchild.generation)

    def test_deeper_reassignment_propagates_new_generation(self):
        # Move mid_a under a deeper root so its own + its descendant's
        # generation must shift upward.
        root_a = build_person(self.clan, ho_ten='Gốc', generation=1)
        deep_parent = build_person(self.clan, ho_ten='Sâu 1', father=root_a, generation=2)
        deep_parent_2 = build_person(self.clan, ho_ten='Sâu 2', father=deep_parent, generation=3)
        mid_a = build_person(self.clan, ho_ten='Giữa', generation=1)
        grandchild = build_person(self.clan, ho_ten='Cháu', father=mid_a, generation=2)

        response = client_for(self.fixture['editor']).patch(
            person_url(self.clan.id, mid_a.id), {'father_id': deep_parent_2.id}, format='json',
        )
        self.assertEqual(200, response.status_code)

        mid_a.refresh_from_db()
        grandchild.refresh_from_db()
        self.assertEqual(4, mid_a.generation)
        self.assertEqual(5, grandchild.generation)

    def test_unrelated_person_not_touched_by_recompute(self):
        root_a = build_person(self.clan, ho_ten='Gốc', generation=1)
        mid_a = build_person(self.clan, ho_ten='Giữa', father=root_a, generation=2)
        untouched = build_person(self.clan, ho_ten='Không liên quan', generation=99)

        client_for(self.fixture['editor']).patch(
            person_url(self.clan.id, mid_a.id), {'ho_ten': 'Giữa (đổi tên)'}, format='json',
        )
        untouched.refresh_from_db()
        self.assertEqual(99, untouched.generation)


class RecomputeGenerationsCommandTests(TestCase):
    def test_recomputes_one_clan(self):
        fixture = build_clan_fixture(suffix='_cmd_one')
        clan = fixture['clan']
        root = build_person(clan, ho_ten='Gốc', generation=None)
        child = build_person(clan, ho_ten='Con', father=root, generation=None)

        call_command('recompute_generations', str(clan.id))

        root.refresh_from_db()
        child.refresh_from_db()
        self.assertEqual(1, root.generation)
        self.assertEqual(2, child.generation)

    def test_recomputes_all_clans(self):
        fixture_1 = build_clan_fixture(suffix='_cmd_all_1')
        fixture_2 = build_clan_fixture(suffix='_cmd_all_2')
        root_1 = build_person(fixture_1['clan'], ho_ten='Gốc 1', generation=None)
        root_2 = build_person(fixture_2['clan'], ho_ten='Gốc 2', generation=None)

        call_command('recompute_generations', '--all')

        root_1.refresh_from_db()
        root_2.refresh_from_db()
        self.assertEqual(1, root_1.generation)
        self.assertEqual(1, root_2.generation)

    def test_requires_clan_id_or_all(self):
        with self.assertRaises(Exception):
            call_command('recompute_generations')

    def test_rejects_unknown_clan_id(self):
        with self.assertRaises(Exception):
            call_command('recompute_generations', '999999')
