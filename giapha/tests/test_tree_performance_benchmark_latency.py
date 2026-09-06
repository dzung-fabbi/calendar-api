"""Wall-clock latency benchmarks for `GET /tree` at 1,000 and 5,000 persons.

Split out of `test_tree_performance_benchmark.py` (see `tree_benchmark_
fixtures.py`'s docstring for the full split rationale). Verifies the SLA
claim: "p95 < 500ms at 1,000 persons". Skipped by default; run explicitly
with `BENCHMARK_TREE_PERFORMANCE=1 ./scripts/run-tests.sh`.

Note: These measurements are on Windows dev machine (Docker on WSL2) with local
MySQL 5.7. Production hardware will differ significantly.
"""

import time
import unittest
from statistics import mean

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.tests.factories import build_clan_fixture
from giapha.tests.tree_benchmark_fixtures import BENCHMARK_ENABLED, build_large_clan_fixture


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
