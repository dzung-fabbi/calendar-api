"""Cost of `recompute_descendant_generations` at the tree root, worst case.

Split out of `test_tree_performance_benchmark.py` (see `tree_benchmark_
fixtures.py`'s docstring for the full split rationale). Skipped by default;
run explicitly with `BENCHMARK_TREE_PERFORMANCE=1 ./scripts/run-tests.sh`.
"""

import time
import unittest

from django.test import TestCase

from giapha.models import Person
from giapha.tests.factories import build_clan_fixture
from giapha.tests.tree_benchmark_fixtures import BENCHMARK_ENABLED, build_large_clan_fixture


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
