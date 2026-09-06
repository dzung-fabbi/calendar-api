"""Performance benchmarks for GET /tree endpoint at scale.

This test suite measures latency, query counts, and time distribution for the
tree endpoint under realistic fixture sizes (1,000 and 5,000 persons). Designed
to verify the SLA claim: "p95 < 500ms at 1,000 persons".

These benchmarks are SKIPPED by default to avoid slowing the test suite.
Run explicitly with: `python manage.py test --settings=djangopj.settings_test \
  giapha.tests.test_tree_performance_benchmark --keep-test-db -v 2`

Or set env var: `BENCHMARK_TREE_PERFORMANCE=1 ./scripts/run-tests.sh`

`TreeCiRegressionGuardTests` at the bottom of this file is DIFFERENT from the
above and runs ALWAYS (not gated by `BENCHMARK_TREE_PERFORMANCE`): phase 10
needs a permanent CI check that `GET /tree` has not regressed to a worse
complexity class at ~1,000 persons, with a deliberately generous threshold
(catch a O(n) or worse regression, not benchmark steady-state latency -- CI
machines are slower and noisier than a dev box). It reuses
`giapha.tests.perf_fixture` (real relations: generations, branches, polygamy,
dead people, an adopted child) rather than `build_large_clan_fixture` below,
which exists only for the opt-in latency benchmarks and is not relations-rich
in the same way.

Fixture sizes are chosen to stress the tree generation algorithm and JSON
serialization without exhausting test machine resources:
- 1,000 persons: realistic large family, target for p95 measurement
- 5,000 persons: ceiling (MAX_CLAN_PERSONS), for worst-case observation

Note: These measurements are on Windows dev machine (Docker on WSL2) with local
MySQL 5.7. Production hardware will differ significantly.
"""

import datetime as dt
import json
import os
import sys
import time
import unittest
from statistics import mean, quantiles

from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.models import Marriage, Person
from giapha.tests.factories import build_clan_fixture, build_person
from giapha.tests.perf_fixture import build_perf_clan_fixture


def should_run_benchmarks():
    """Skip benchmarks unless explicitly enabled."""
    return os.environ.get('BENCHMARK_TREE_PERFORMANCE') == '1'


def build_large_clan_fixture(clan, num_persons=1000, branching_factor=2.5):
    """Build a realistic multi-generational clan fixture of `num_persons` persons.

    Uses a branching factor to create roughly `branching_factor` children per
    parent on average, resulting in a plausible generational tree. Adds marriages
    between generations to create more edges without proportionally increasing
    person count.

    Args:
        clan: A Clan instance.
        num_persons: Target number of persons to create.
        branching_factor: Average children per parent (typically 2-3 for realistic
            family structures).

    Returns:
        dict with 'persons' (list of Person instances) and metadata.
    """
    if num_persons < 10:
        raise ValueError("Must generate at least 10 persons for meaningful test")

    persons = []
    persons_by_generation = {}  # generation -> list of Person IDs

    # Start with a single root (generation 1)
    root = build_person(clan, ho_ten='Tổ tiên')
    persons.append(root)
    persons_by_generation[1] = [root.id]

    current_gen = 1
    max_generations = 10  # Enough to reach 5000+ with reasonable branching

    # Build generations bottom-up via branching
    while len(persons) < num_persons and current_gen < max_generations:
        parents = persons_by_generation[current_gen]
        next_gen_count = int(len(parents) * branching_factor)
        # Ensure we don't vastly overshoot
        next_gen_count = min(next_gen_count, num_persons - len(persons) + 100)

        persons_by_generation[current_gen + 1] = []

        # Distribute children among parents
        children_per_parent = max(1, int(next_gen_count / len(parents)))
        parent_idx = 0

        for _ in range(next_gen_count):
            if len(persons) >= num_persons:
                break
            parent = Person.objects.get(id=parents[parent_idx])
            child = build_person(
                clan,
                ho_ten=f'Gen{current_gen + 1}_Child{len(persons)}',
                father=parent,
                gioi_tinh=('nu' if len(persons) % 2 == 0 else 'nam'),
            )
            persons.append(child)
            persons_by_generation[current_gen + 1].append(child.id)

            parent_idx = (parent_idx + 1) % len(parents)

        # Add marriages within/between generations for realism
        # (marriage within same gen, or between adjacent gens)
        if persons_by_generation.get(current_gen):
            gen_persons = list(
                Person.objects.filter(id__in=persons_by_generation[current_gen])
            )
            for i in range(0, len(gen_persons) - 1, 2):
                husband = gen_persons[i]
                wife_idx = min(i + 1, len(gen_persons) - 1)
                wife = gen_persons[wife_idx]
                if husband.gioi_tinh == 'nam' and wife.gioi_tinh == 'nu' and husband.id != wife.id:
                    try:
                        Marriage.objects.create(
                            husband=husband, wife=wife, status='dang_ket_hon'
                        )
                    except Exception:
                        pass  # Duplicate marriage or other constraint violation

        current_gen += 1

    return {
        'persons': persons,
        'num_persons': len(persons),
        'num_generations': current_gen,
        'persons_by_generation': persons_by_generation,
    }


# Mark benchmark test classes to skip unless benchmarks are explicitly enabled
BENCHMARK_ENABLED = should_run_benchmarks()


@unittest.skipUnless(BENCHMARK_ENABLED, "Benchmarks skipped unless BENCHMARK_TREE_PERFORMANCE=1")
class TreePerformanceBenchmark1000(TestCase):
    """Measure GET /tree latency at 1,000 persons (primary SLA target)."""

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_bench_1k')
        cls.clan = cls.fixture['clan']
        cls.fixture_data = build_large_clan_fixture(cls.clan, num_persons=1000)
        cls.user = cls.fixture['viewer']

    def test_tree_1000_persons_latency_and_query_budget(self):
        """Measure p95 latency at 1,000 persons with query count assertion."""
        client = APIClient()
        client.force_authenticate(user=self.user)
        url = reverse('clan-tree', kwargs={'clan_id': self.clan.id})

        # Warm-up (discard, so we're measuring steady-state, not cold cache)
        client.get(url)

        # Measure latency across 20 samples
        latencies_ms = []
        sample_count = 20

        for _ in range(sample_count):
            start = time.perf_counter()
            response = client.get(url)
            elapsed_ms = (time.perf_counter() - start) * 1000

            self.assertEqual(200, response.status_code)
            latencies_ms.append(elapsed_ms)

        # Confirm query count still meets budget on final request
        with self.assertNumQueries(3):
            response = client.get(url)
        self.assertEqual(200, response.status_code)

        # Compute stats
        latencies_sorted = sorted(latencies_ms)
        p50 = latencies_sorted[len(latencies_sorted) // 2]
        p95_idx = int(len(latencies_sorted) * 0.95)
        p95 = latencies_sorted[min(p95_idx, len(latencies_sorted) - 1)]
        p99 = latencies_sorted[int(len(latencies_sorted) * 0.99)]
        max_latency = max(latencies_ms)
        avg_latency = mean(latencies_ms)

        # Measure response payload size
        response = client.get(url)
        payload_bytes = len(response.content)

        # Verify node count and edge count
        body = response.json()
        node_count = len(body['nodes'])
        edge_count = len(body['edges'])

        print(f"\n{'='*60}")
        print(f"TREE PERFORMANCE AT 1,000 PERSONS")
        print(f"{'='*60}")
        print(f"Fixture shape: {self.fixture_data['num_persons']} persons, "
              f"{self.fixture_data['num_generations']} generations")
        print(f"Nodes in response: {node_count}")
        print(f"Edges in response: {edge_count}")
        print(f"Payload size: {payload_bytes:,} bytes (~{payload_bytes / 1024 / 1024:.2f} MB)")
        print(f"\nLatency (n={sample_count}):")
        print(f"  p50:  {p50:.1f}ms")
        print(f"  p95:  {p95:.1f}ms  {'PASS ✓' if p95 < 500 else 'FAIL ✗'}")
        print(f"  p99:  {p99:.1f}ms")
        print(f"  max:  {max_latency:.1f}ms")
        print(f"  avg:  {avg_latency:.1f}ms")
        print(f"\nQuery count: 3 (auth + persons + marriages)")
        print(f"truncated: {body['truncated']}")
        print(f"{'='*60}\n")

        # Assert the target SLA
        self.assertLess(
            p95, 500,
            f"p95 latency {p95:.1f}ms exceeds target 500ms at 1,000 persons",
        )

    def test_tree_1000_persons_response_validity(self):
        """Spot-check response structure and content."""
        client = APIClient()
        client.force_authenticate(user=self.user)
        url = reverse('clan-tree', kwargs={'clan_id': self.clan.id})

        response = client.get(url)
        self.assertEqual(200, response.status_code)

        body = response.json()
        self.assertIn('clan', body)
        self.assertIn('nodes', body)
        self.assertIn('edges', body)
        self.assertIn('truncated', body)
        self.assertIsInstance(body['nodes'], list)
        self.assertIsInstance(body['edges'], list)
        self.assertFalse(body['truncated'])

        # Spot-check first few nodes
        if body['nodes']:
            node = body['nodes'][0]
            for required_field in ('id', 'ho_ten', 'generation', 'gioi_tinh'):
                self.assertIn(required_field, node)


@unittest.skipUnless(BENCHMARK_ENABLED, "Benchmarks skipped unless BENCHMARK_TREE_PERFORMANCE=1")
class TreePerformanceBenchmark5000(TestCase):
    """Measure GET /tree at 5,000 persons (MAX_CLAN_PERSONS ceiling)."""

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_bench_5k')
        cls.clan = cls.fixture['clan']
        cls.fixture_data = build_large_clan_fixture(cls.clan, num_persons=5000)
        cls.user = cls.fixture['viewer']

    def test_tree_5000_persons_latency_and_query_budget(self):
        """Measure latency at 5,000 persons (worst-case within deployment limit)."""
        client = APIClient()
        client.force_authenticate(user=self.user)
        url = reverse('clan-tree', kwargs={'clan_id': self.clan.id})

        # Warm-up
        client.get(url)

        # Measure 10 samples (fewer than 1K case, since 5K is slower)
        latencies_ms = []
        sample_count = 10

        for _ in range(sample_count):
            start = time.perf_counter()
            response = client.get(url)
            elapsed_ms = (time.perf_counter() - start) * 1000

            self.assertEqual(200, response.status_code)
            latencies_ms.append(elapsed_ms)

        # Confirm query budget
        with self.assertNumQueries(3):
            response = client.get(url)

        latencies_sorted = sorted(latencies_ms)
        p50 = latencies_sorted[len(latencies_sorted) // 2]
        p95_idx = max(0, int(len(latencies_sorted) * 0.95) - 1)
        p95 = latencies_sorted[p95_idx]
        max_latency = max(latencies_ms)
        avg_latency = mean(latencies_ms)

        response = client.get(url)
        payload_bytes = len(response.content)
        body = response.json()
        node_count = len(body['nodes'])
        edge_count = len(body['edges'])

        print(f"\n{'='*60}")
        print(f"TREE PERFORMANCE AT 5,000 PERSONS (CEILING)")
        print(f"{'='*60}")
        print(f"Fixture shape: {self.fixture_data['num_persons']} persons, "
              f"{self.fixture_data['num_generations']} generations")
        print(f"Nodes in response: {node_count}")
        print(f"Edges in response: {edge_count}")
        print(f"Payload size: {payload_bytes:,} bytes (~{payload_bytes / 1024 / 1024:.2f} MB)")
        print(f"\nLatency (n={sample_count}):")
        print(f"  p50:  {p50:.1f}ms")
        print(f"  p95:  {p95:.1f}ms")
        print(f"  max:  {max_latency:.1f}ms")
        print(f"  avg:  {avg_latency:.1f}ms")
        print(f"\nQuery count: 3 (auth + persons + marriages)")
        print(f"truncated: {body['truncated']}")
        print(f"{'='*60}\n")

        # Verify query count
        self.assertIsNotNone(response)  # placeholder assertion


@unittest.skipUnless(BENCHMARK_ENABLED, "Benchmarks skipped unless BENCHMARK_TREE_PERFORMANCE=1")
class RecomputeGenerationsWorstCase(TestCase):
    """Measure recompute_descendant_generations cost at tree root (worst case)."""

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_bench_recompute')
        cls.clan = cls.fixture['clan']
        cls.fixture_data = build_large_clan_fixture(cls.clan, num_persons=1000)
        cls.user = cls.fixture['viewer']

    def test_recompute_at_root_worst_case(self):
        """Measure recompute_descendant_generations when triggered at tree root.

        This is the worst case: recomputing a root person forces recomputation
        of the entire subtree (almost the entire clan if root is near the top).
        """
        from giapha.selectors.tree import recompute_descendant_generations

        # Find the oldest generation (likely roots)
        root_candidates = Person.objects.filter(
            clan=self.clan, is_deleted=False, father__isnull=True, mother__isnull=True
        ).order_by('id')[:5]

        if not root_candidates.exists():
            self.skipTest("No roots found in fixture")

        root = root_candidates.first()

        # Measure recompute cost
        start = time.perf_counter()
        changed_count = recompute_descendant_generations(self.clan.id, root.id)
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n{'='*60}")
        print(f"RECOMPUTE_DESCENDANT_GENERATIONS WORST CASE (1,000 PERSONS)")
        print(f"{'='*60}")
        print(f"Triggered at root: {root.ho_ten} (id={root.id})")
        print(f"Changed rows: {changed_count}")
        print(f"Elapsed time: {elapsed_ms:.1f}ms")
        print(f"Status: {'PASS ✓ (< 1s)' if elapsed_ms < 1000 else 'WARN ⚠ (potential timeout risk)'}")
        print(f"{'='*60}\n")

        # Assert it completes in reasonable time (not in SLA, just sanity check)
        self.assertLess(
            elapsed_ms, 5000,
            f"Recompute at root took {elapsed_ms:.1f}ms, risks timeout in request",
        )


class TreeCiRegressionGuardTests(TestCase):
    """Always-on CI guard (not gated by `BENCHMARK_TREE_PERFORMANCE`): `GET
    /tree` over a ~1,000-person clan with real relations must not regress to
    a worse complexity class. See the module docstring for why this is
    separate from the opt-in latency benchmarks above.

    The threshold is deliberately generous (2s, not the 500ms p95 SLA the
    benchmarks above track) -- the goal is catching an accidental N+1 or a
    quadratic pass over the person list, not measuring steady-state latency
    on noisy CI hardware.
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
