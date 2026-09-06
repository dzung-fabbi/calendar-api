"""Query-count ratchet for the 2 of 7 budgeted endpoints that do NOT meet
their nominal ceiling from the phase-10 spec -- split from
`test_query_counts.py` (see that file's docstring) purely so each can carry
its explanation without pushing the file over the size guideline.

Shares `QueryBudgetTestCase` (fixtures + ratchet helper) and `client_for`
from `test_query_counts.py`.
"""

from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.tests.public_helpers import enable_public_link
from giapha.tests.test_query_counts import QueryBudgetTestCase, client_for


class XungHoBudgetTests(QueryBudgetTestCase):
    """`GET /clans/{id}/xung-ho` -- nominal ceiling 2, MEASURED 3 here.

    Phase 7 already recorded that this endpoint does not meet its <=2
    budget: the common case is role check + `clan_kinship_rows` (2), but
    every request in this test omits `a`, which adds the `member_binding`
    lookup (3). A request about an in-law (no blood link) would add a 4th
    (`clan_spouse_pairs`), the documented worst case in `views/kinship.py`'s
    module docstring -- not exercised here since the fixture's bound viewer
    has a blood link to `parent`/`roots[0]`. Recording the honest number
    (3), not silently keeping a "2" that the endpoint has never actually
    achieved with an unbound `a`.
    """

    def test_xung_ho_budget(self):
        small = self.query_count(
            client_for(self.small['viewer']),
            reverse('clan-xung-ho', kwargs={'clan_id': self.small_clan.id}),
            {'b': self.grandparent.id},
        )
        large = self.query_count(
            client_for(self.large['viewer']),
            reverse('clan-xung-ho', kwargs={'clan_id': self.large_clan.id}),
            {'b': self.large_perf['persons'][2].id},
        )
        self.assert_budget(
            'xung_ho', small, large,
            'Ceiling in the phase-10 spec is 2; actual is 3 for an unbound `a` '
            '(binding lookup), 4 for an in-law pair -- see class docstring.',
        )


class PublicTreeBudgetTests(QueryBudgetTestCase):
    """`GET /public/{slug}/tree` -- nominal ceiling 3, MEASURED 4 here.

    `public_tree_payload` (selectors/public.py) is: clan-by-slug lookup (1)
    + id/liveness scan (1) + one requery PER non-empty liveness branch (0-2).
    Phase 9 measured 3-4; this fixture has both living and dead people (the
    perf fixture marks every 7th person dead), so it costs 4, not 3. Recording
    the honest number instead of picking a fixture that happens to hit 3.
    """

    def setUp(self):
        super().setUp()
        # `public/...` is `ScopedRateThrottle`-limited per IP (scope
        # `giapha-public`), backed by the process-wide `LocMemCache` -- an
        # earlier public-endpoint test class in the same run would otherwise
        # leave this class's very first request already throttled (429, not
        # 200). Same fix as `giapha.tests.public_helpers.PublicEndpointTestCase`,
        # applied by hand since this class needs `QueryBudgetTestCase`'s
        # fixture, not that mixin's.
        cache.clear()

    def test_public_tree_budget(self):
        small_slug = enable_public_link(self.small_clan)
        large_slug = enable_public_link(self.large_clan)

        small = self.query_count(APIClient(), reverse('public-clan-tree', kwargs={'slug': small_slug}))
        large = self.query_count(APIClient(), reverse('public-clan-tree', kwargs={'slug': large_slug}))
        self.assert_budget(
            'public_tree', small, large,
            'Ceiling in the phase-10 spec is 3; actual is 4 when the clan has '
            'both living and dead people -- see class docstring.',
        )
