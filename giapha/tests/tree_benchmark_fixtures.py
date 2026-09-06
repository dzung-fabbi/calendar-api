"""Shared fixture builder + gate helper for the `/tree` performance benchmark
suite, split out of `test_tree_performance_benchmark.py` (was 586 lines,
`docs/code-standards.md` caps files at 200) into:

- `tree_benchmark_fixtures.py` (this file): the gate + the synthetic large-clan
  builder, no test classes -- Django's test runner only discovers `Test*`
  classes, so this module is never collected as a suite on its own.
- `test_tree_performance_benchmark_latency.py`: p50/p95/p99 wall-clock at
  1,000 and 5,000 persons.
- `test_tree_recompute_benchmark.py`: `recompute_descendant_generations`
  worst-case cost.
- `test_tree_performance_benchmark_stage_profile.py`: DB vs Python vs
  serializer vs JSON-render attribution.
- `test_tree_ci_regression_guard.py`: the ALWAYS-ON (not gated) complexity
  regression guard, using `giapha.tests.perf_fixture` instead of the
  synthetic builder below -- see that test file's docstring for why.

All benchmark test classes except the CI regression guard stay gated behind
`BENCHMARK_TREE_PERFORMANCE=1`, unchanged from before the split:
`BENCHMARK_TREE_PERFORMANCE=1 ./scripts/run-tests.sh`.
"""

import os

from giapha.models import Marriage, Person
from giapha.tests.factories import build_person


def should_run_benchmarks():
    """Skip benchmarks unless explicitly enabled."""
    return os.environ.get('BENCHMARK_TREE_PERFORMANCE') == '1'


# Mark benchmark test classes to skip unless benchmarks are explicitly enabled.
BENCHMARK_ENABLED = should_run_benchmarks()


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
