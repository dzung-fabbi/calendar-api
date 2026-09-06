"""Attributes `GET /tree` latency to DB fetch vs Python shaping vs
serialization, rather than reporting a single opaque wall-clock number.

Split out of `test_tree_performance_benchmark.py` (see `tree_benchmark_
fixtures.py`'s docstring for the full split rationale). Skipped by default;
run explicitly with `BENCHMARK_TREE_PERFORMANCE=1 ./scripts/run-tests.sh`.

Method: `tree_payload()` is timed whole, then the two `.values()` queries it
runs are re-timed in isolation with the same filters; the difference is the
pure-Python part (`compute_generations` + `node_from_row` +
`*_edges_from_rows`). Serialization is timed separately as
`TreeSerializer(...).data` followed by a `JSONRenderer().render(...)`, which
is what the view actually pays.

Stage boundaries here mirror `selectors.tree.tree_payload`; if that
function's query shape changes, the DB re-timing below must be updated to
match or the attribution silently drifts.
"""

import time
import unittest

from django.test import TestCase

from giapha.models import Marriage as MarriageModel
from giapha.models import Person
from giapha.tests.factories import build_clan_fixture
from giapha.tests.tree_benchmark_fixtures import BENCHMARK_ENABLED, build_large_clan_fixture


@unittest.skipUnless(BENCHMARK_ENABLED, "Benchmarks skipped unless BENCHMARK_TREE_PERFORMANCE=1")
class TreeStageProfileTests(TestCase):
    """Median-of-10 DB / Python / serializer / render split at 1,000 persons."""

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_bench_profile')
        cls.clan = cls.fixture['clan']
        cls.fixture_data = build_large_clan_fixture(cls.clan, num_persons=1000)

    def _profile_once(self, clan_id, max_persons):
        from rest_framework.renderers import JSONRenderer

        from giapha.selectors.tree import _ROW_FIELDS, tree_payload
        from giapha.serializers.tree import TreeSerializer

        # Stage 1+2 together: DB round trips + all pure-Python shaping.
        start = time.perf_counter()
        payload = tree_payload(clan_id, max_persons=max_persons)
        payload_ms = (time.perf_counter() - start) * 1000

        # Re-time ONLY the DB round trips, same filters as the selector.
        start = time.perf_counter()
        person_rows = list(
            Person.objects.filter(clan_id=clan_id, is_deleted=False)
            .order_by('id')
            .values(*_ROW_FIELDS, 'clan__ten_ho')[:max_persons + 1]
        )
        marriage_rows = list(
            MarriageModel.objects.filter(husband__clan_id=clan_id)
            .values('husband_id', 'wife_id', 'order', 'status')
        )
        db_ms = (time.perf_counter() - start) * 1000

        # Stage 3: serializer field coercion, then JSON encoding.
        start = time.perf_counter()
        data = TreeSerializer(payload).data
        serializer_ms = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        rendered = JSONRenderer().render(data)
        render_ms = (time.perf_counter() - start) * 1000

        return {
            'payload_ms': payload_ms,
            'db_ms': db_ms,
            'python_ms': max(0.0, payload_ms - db_ms),
            'serializer_ms': serializer_ms,
            'render_ms': render_ms,
            'payload_bytes': len(rendered),
            'node_count': len(payload['nodes']),
            'edge_count': len(payload['edges']),
            'person_rows': len(person_rows),
            'marriage_rows': len(marriage_rows),
        }

    def test_stage_breakdown_at_1000_persons(self):
        """Print a measured DB / Python / serialization split, median of 10."""
        clan_id = self.clan.id
        max_persons = 5000

        # Warm-up: first call pays connection + query-plan costs.
        self._profile_once(clan_id, max_persons)

        samples = [self._profile_once(clan_id, max_persons) for _ in range(10)]

        def median_of(key):
            values = sorted(s[key] for s in samples)
            return values[len(values) // 2]

        db_ms = median_of('db_ms')
        python_ms = median_of('python_ms')
        serializer_ms = median_of('serializer_ms')
        render_ms = median_of('render_ms')
        total_ms = db_ms + python_ms + serializer_ms + render_ms

        first = samples[0]

        def pct(value):
            return (value / total_ms * 100) if total_ms else 0.0

        print("\n" + "=" * 60)
        print("STAGE PROFILE AT 1,000 PERSONS (median of 10)")
        print("=" * 60)
        print("Nodes: {}  Edges: {}".format(first['node_count'], first['edge_count']))
        print("Person rows fetched: {}  Marriage rows fetched: {}".format(
            first['person_rows'], first['marriage_rows']))
        print("Rendered payload: {:,} bytes".format(first['payload_bytes']))
        print("")
        print("  DB fetch (2 queries):     {:6.1f}ms  ({:4.1f}%)".format(db_ms, pct(db_ms)))
        print("  Python shaping:           {:6.1f}ms  ({:4.1f}%)".format(python_ms, pct(python_ms)))
        print("  Serializer coercion:      {:6.1f}ms  ({:4.1f}%)".format(
            serializer_ms, pct(serializer_ms)))
        print("  JSON render:              {:6.1f}ms  ({:4.1f}%)".format(render_ms, pct(render_ms)))
        print("  " + "-" * 46)
        print("  Sum of stages:            {:6.1f}ms".format(total_ms))
        print("=" * 60 + "\n")

        # No SLA assertion here -- this test exists to attribute time, and the
        # p95 gate lives in TreePerformanceBenchmark1000. Assert only that the
        # attribution is coherent (every stage measured, nothing negative).
        for key in ('db_ms', 'python_ms', 'serializer_ms', 'render_ms'):
            self.assertGreaterEqual(median_of(key), 0.0)
        self.assertGreater(total_ms, 0.0)


@unittest.skipUnless(BENCHMARK_ENABLED, "Benchmarks skipped unless BENCHMARK_TREE_PERFORMANCE=1")
class TreeStageProfileAtCeilingTests(TreeStageProfileTests):
    """Same stage attribution as `TreeStageProfileTests`, at the 5,000-person
    ceiling -- confirms whether the serializer-dominated split holds at the
    top of the supported range instead of assuming it scales linearly.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_bench_profile_5k')
        cls.clan = cls.fixture['clan']
        cls.fixture_data = build_large_clan_fixture(cls.clan, num_persons=5000)

    def test_stage_breakdown_at_1000_persons(self):
        """Not applicable -- this subclass carries a 5,000-person fixture."""
        self.skipTest('covered by test_stage_breakdown_at_ceiling')

    def test_stage_breakdown_at_ceiling(self):
        clan_id = self.clan.id
        max_persons = 5000

        self._profile_once(clan_id, max_persons)
        samples = [self._profile_once(clan_id, max_persons) for _ in range(5)]

        def median_of(key):
            values = sorted(s[key] for s in samples)
            return values[len(values) // 2]

        db_ms = median_of('db_ms')
        python_ms = median_of('python_ms')
        serializer_ms = median_of('serializer_ms')
        render_ms = median_of('render_ms')
        total_ms = db_ms + python_ms + serializer_ms + render_ms
        first = samples[0]

        def pct(value):
            return (value / total_ms * 100) if total_ms else 0.0

        print("\n" + "=" * 60)
        print("STAGE PROFILE AT CEILING (median of 5)")
        print("=" * 60)
        print("Nodes: {}  Edges: {}".format(first['node_count'], first['edge_count']))
        print("Rendered payload: {:,} bytes".format(first['payload_bytes']))
        print("")
        print("  DB fetch (2 queries):     {:6.1f}ms  ({:4.1f}%)".format(db_ms, pct(db_ms)))
        print("  Python shaping:           {:6.1f}ms  ({:4.1f}%)".format(python_ms, pct(python_ms)))
        print("  Serializer coercion:      {:6.1f}ms  ({:4.1f}%)".format(
            serializer_ms, pct(serializer_ms)))
        print("  JSON render:              {:6.1f}ms  ({:4.1f}%)".format(render_ms, pct(render_ms)))
        print("  " + "-" * 46)
        print("  Sum of stages:            {:6.1f}ms".format(total_ms))
        print("=" * 60 + "\n")

        self.assertGreater(total_ms, 0.0)
