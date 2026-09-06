"""Always-on `GET /tree` complexity regression guard.

Split out of `test_tree_performance_benchmark.py` (see `tree_benchmark_
fixtures.py`'s docstring for the full split rationale). UNLIKE every other
file in that split, `TreeCiRegressionGuardTests` below is NOT gated by
`BENCHMARK_TREE_PERFORMANCE` -- phase 10 needs a permanent CI check that
`GET /tree` has not regressed to a worse complexity class at ~1,000 persons,
with a deliberately generous threshold (catch a O(n) or worse regression,
not benchmark steady-state latency -- CI machines are slower and noisier
than a dev box). It reuses `giapha.tests.perf_fixture` (real relations:
generations, branches, polygamy, dead people, an adopted child) rather than
`tree_benchmark_fixtures.build_large_clan_fixture`, which exists only for the
opt-in latency benchmarks and is not relations-rich in the same way.
"""

import time

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.tests.factories import build_clan_fixture
from giapha.tests.perf_fixture import build_perf_clan_fixture


class TreeCiRegressionGuardTests(TestCase):
    """Always-on CI guard (not gated by `BENCHMARK_TREE_PERFORMANCE`): `GET
    /tree` over a ~1,000-person clan with real relations must not regress to
    a worse complexity class.

    The threshold is deliberately generous (2s, not the 500ms p95 SLA the
    benchmarks in the sibling files track) -- the goal is catching an
    accidental N+1 or a quadratic pass over the person list, not measuring
    steady-state latency on noisy CI hardware.
    """

    CI_THRESHOLD_SECONDS = 2.0

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_ci_guard')
        cls.clan = cls.fixture['clan']
        cls.perf = build_perf_clan_fixture(cls.clan, target_size=1000)

    def test_tree_endpoint_completes_within_generous_ci_threshold(self):
        client = APIClient()
        client.force_authenticate(user=self.fixture['viewer'])
        url = reverse('clan-tree', kwargs={'clan_id': self.clan.id})

        start = time.perf_counter()
        response = client.get(url)
        elapsed_seconds = time.perf_counter() - start

        self.assertEqual(200, response.status_code)
        body = response.json()
        # Sanity: the fixture's relations actually made it into the response,
        # so a future change that silently drops rows still fails loudly.
        self.assertGreaterEqual(len(body['nodes']), self.perf['total'])
        self.assertFalse(body['truncated'])
        self.assertLess(
            elapsed_seconds, self.CI_THRESHOLD_SECONDS,
            '/tree took {:.2f}s for {} persons, exceeds the {}s CI regression '
            'guard threshold.'.format(elapsed_seconds, self.perf['total'], self.CI_THRESHOLD_SECONDS),
        )
