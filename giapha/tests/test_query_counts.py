"""Query-count ratchet for 5 of the 7 budgeted endpoints (phase 10 spec).

The other 2 (`xung-ho`, `public/{slug}/tree`) live in
`test_query_counts_over_budget.py` -- split out because both are NOT within
their nominal ceiling and need a paragraph of explanation each, which would
push this file over the size guideline alongside the other five. Both files
share `QueryBudgetTestCase` (defined here) for its fixtures and ratchet
helper.

Reuses the same ratchet mechanism as `apis/tests/test_query_counts.py`
(budget recorded once into `snapshots/query_budgets.json`, later runs may
only be <= it) via `giapha.tests.shape`, the adapter binding the shared
`testkit.shape` engine to this app's own snapshot directory.

Every budget is asserted against BOTH a small fixture (a handful of persons)
and the ~1,000-person `perf_fixture` (real relations: several generations,
branches, polygamy, dead people) -- proving the count is O(1) in clan size,
not merely "acceptable on today's tiny fixture". A fixture without real
relations populated makes an N+1 look fixed when it is not
(`apis/tests/factories.py`'s docstring).
"""

import datetime as dt

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.models import Marriage
from giapha.tests.factories import bind_member, build_clan_fixture, build_person
from giapha.tests.perf_fixture import build_perf_clan_fixture
from giapha.tests.shape import load_snapshot, save_snapshot

BUDGETS = 'query_budgets'


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class QueryBudgetTestCase(TestCase):
    """Shared small + large fixture and the ratchet-assert helper."""

    @classmethod
    def setUpTestData(cls):
        cls.small = build_clan_fixture(suffix='_qc_small')
        cls.small_clan = cls.small['clan']
        # `grandparent` carries a complete death record on purpose: the
        # public-tree budget (see `test_query_counts_over_budget.py`)
        # branches on whether ANY dead/living person is present, so a small
        # fixture with only living people would exercise a different code
        # path than the (deliberately mixed) perf fixture and make an
        # unrelated data difference look like a clan-size effect.
        cls.grandparent = build_person(
            cls.small_clan, ho_ten='Cụ', death_solar=dt.date(1980, 1, 1),
            death_lunar_day=1, death_lunar_month=1,
        )
        cls.parent = build_person(cls.small_clan, ho_ten='Ông', father=cls.grandparent)
        build_person(cls.small_clan, ho_ten='Cháu', father=cls.parent)
        spouse = build_person(cls.small_clan, ho_ten='Vợ ông', gioi_tinh='nu')
        Marriage.objects.create(husband=cls.parent, wife=spouse, status='dang_ket_hon')
        bind_member(cls.small_clan, cls.small['viewer'], cls.parent)

        cls.large = build_clan_fixture(suffix='_qc_large')
        cls.large_clan = cls.large['clan']
        cls.large_perf = build_perf_clan_fixture(cls.large_clan, target_size=1000)
        bind_member(cls.large_clan, cls.large['viewer'], cls.large_perf['roots'][0])

    def query_count(self, client, path, params=None):
        with CaptureQueriesContext(connection) as captured:
            response = client.get(path, params or {})
        self.assertEqual(200, response.status_code, response.content)
        return len(captured.captured_queries)

    def assert_budget(self, name, small_count, large_count, comment=''):
        """Records/checks the ratchet AND asserts the two fixture sizes cost
        the exact same number of queries -- the property the budget exists
        to prove. `comment` is surfaced in the assertion message for the
        known-over-budget endpoints.
        """
        self.assertEqual(
            small_count, large_count,
            '{} cost {} queries on the small fixture but {} on the ~1,000-person '
            'one -- the budget must not grow with clan size.{}'.format(
                name, small_count, large_count, ' ' + comment if comment else '',
            ),
        )
        budgets = load_snapshot(BUDGETS) or {}
        if name not in budgets:
            budgets[name] = small_count
            save_snapshot(BUDGETS, budgets)
            self.skipTest('Recorded query budget {}={}. Re-run to assert it.'.format(name, small_count))
        self.assertLessEqual(
            small_count, budgets[name],
            '{} used {} queries, budget is {}. If this is an intended regression, '
            'justify it; otherwise it is an N+1.'.format(name, small_count, budgets[name]),
        )


class ClanListBudgetTests(QueryBudgetTestCase):
    """`GET /clans` -- ceiling 2 (`clans_for_user` + `roles_for_clans`)."""

    def test_clans_budget(self):
        small = self.query_count(client_for(self.small['viewer']), reverse('clan-list-create'))
        large = self.query_count(client_for(self.large['viewer']), reverse('clan-list-create'))
        self.assert_budget('clans_list', small, large)


class ClanTreeBudgetTests(QueryBudgetTestCase):
    """`GET /clans/{id}/tree` -- ceiling 3 (role check + Person + Marriage)."""

    def test_tree_budget(self):
        small = self.query_count(
            client_for(self.small['viewer']),
            reverse('clan-tree', kwargs={'clan_id': self.small_clan.id}),
        )
        large = self.query_count(
            client_for(self.large['viewer']),
            reverse('clan-tree', kwargs={'clan_id': self.large_clan.id}),
        )
        self.assert_budget('clan_tree', small, large)


class PersonsListBudgetTests(QueryBudgetTestCase):
    """`GET /clans/{id}/persons` (paginated) -- ceiling 3
    (role check + `LimitOffsetPagination`'s COUNT + page SELECT).
    """

    def test_persons_list_budget(self):
        small = self.query_count(
            client_for(self.small['viewer']),
            reverse('person-list-create', kwargs={'clan_id': self.small_clan.id}),
        )
        large = self.query_count(
            client_for(self.large['viewer']),
            reverse('person-list-create', kwargs={'clan_id': self.large_clan.id}),
        )
        self.assert_budget('persons_list', small, large)


class PersonDetailBudgetTests(QueryBudgetTestCase):
    """`GET /clans/{id}/persons/{pid}` -- ceiling 3
    (role check + `select_related('father', 'mother')` single query).
    """

    def test_person_detail_budget(self):
        small = self.query_count(
            client_for(self.small['viewer']),
            reverse('person-detail', kwargs={'clan_id': self.small_clan.id, 'person_id': self.parent.id}),
        )
        large = self.query_count(
            client_for(self.large['viewer']),
            reverse(
                'person-detail',
                kwargs={'clan_id': self.large_clan.id, 'person_id': self.large_perf['roots'][0].id},
            ),
        )
        self.assert_budget('person_detail', small, large)


class LichGioBudgetTests(QueryBudgetTestCase):
    """`GET /clans/{id}/lich-gio` -- ceiling 2
    (role check + `deceased_with_lunar_death`).
    """

    def test_lich_gio_budget(self):
        small = self.query_count(
            client_for(self.small['viewer']),
            reverse('clan-lich-gio', kwargs={'clan_id': self.small_clan.id}),
        )
        large = self.query_count(
            client_for(self.large['viewer']),
            reverse('clan-lich-gio', kwargs={'clan_id': self.large_clan.id}),
        )
        self.assert_budget('lich_gio', small, large)
