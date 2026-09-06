"""Builds a ~1,000-person clan with REAL relations, for two consumers:

- `test_tree_performance_benchmark.py`'s CI-facing timing test (`GET /tree`
  must stay under a generous ceiling at this scale);
- `test_query_counts.py`'s "budget does not grow with clan size" assertion.

Populating real relations (parents every generation, marriages including a
polygamous one, dead people with complete lunar death dates, an adopted
child) is the point, not incidental: a flat pile of unrelated Person rows
would make an N+1 in the tree/query-count code look fixed when it is not --
`apis/tests/factories.py`'s module docstring records the same lesson for the
sibling app's fixtures.

Uses `bulk_create` per generation (not `Person.objects.create()` in a loop)
so building 1,000 rows stays fast enough to run on every `giapha` suite
invocation, not just in an opt-in benchmark. MySQL's bulk_create does not
report back the inserted ids (only PostgreSQL does), so each generation's
rows are re-fetched by `ho_ten` -- unique per row by construction -- right
after inserting them, to get real ids for the next generation's `father_id`.
"""

import datetime as dt

from giapha.models import Marriage, Person
from giapha.tests.factories import build_person

BRANCHES = ('Chi trưởng', 'Chi thứ')
GENERATIONS = 5
# Every 7th person (arbitrary, just "a real spread, not everyone/no one")
# gets a complete lunar death date, so both dead-person response fields
# and "does the giỗ/public-liveness code scale" get exercised at size.
DEAD_EVERY_NTH = 7


def build_perf_clan_fixture(clan, target_size=1000):
    """Returns `{'roots': [...], 'total': int, 'persons': [Person, ...]}`.

    `total` is the actual row count created (>= `target_size`, since the
    per-generation split is integer division and rounds up in practice).
    """
    roots = [
        build_person(clan, ho_ten='Thuỷ tổ {}'.format(branch), generation=1, branch=branch)
        for branch in BRANCHES
    ]
    all_persons = list(roots)

    for branch_index, branch in enumerate(BRANCHES):
        current_gen_ids = [roots[branch_index].id]
        per_branch_target = max(target_size // len(BRANCHES), 10)
        for generation in range(2, GENERATIONS + 1):
            children_needed = max(per_branch_target // (GENERATIONS - 1), len(current_gen_ids))
            children_per_parent = max(children_needed // len(current_gen_ids), 1)

            batch = []
            for parent_id in current_gen_ids:
                for child_index in range(children_per_parent):
                    batch.append(Person(
                        clan=clan,
                        ho_ten='G{}_B{}_P{}_C{}'.format(generation, branch_index, parent_id, child_index),
                        gioi_tinh=('nu' if child_index % 2 else 'nam'),
                        generation=generation, branch=branch, father_id=parent_id,
                    ))
            Person.objects.bulk_create(batch)
            created = list(Person.objects.filter(clan=clan, ho_ten__in=[p.ho_ten for p in batch]))

            all_persons.extend(created)
            current_gen_ids = [person.id for person in created]

    _add_polygamous_marriage(clan, all_persons)
    _mark_dead_with_lunar_dates(all_persons)
    _mark_one_adopted_child(all_persons)

    return {'roots': roots, 'total': len(all_persons), 'persons': all_persons}


def _add_polygamous_marriage(clan, all_persons):
    """One husband, two wives (`order` 1 and 2) -- the polygamy case the
    tree/kinship rendering must handle without assuming one spouse per Person.
    """
    husband = next(
        (p for p in all_persons if p.gioi_tinh == 'nam' and p.generation == 2), None,
    )
    if husband is None:
        return
    wife_1 = build_person(clan, ho_ten='Vợ cả của {}'.format(husband.ho_ten), gioi_tinh='nu')
    wife_2 = build_person(clan, ho_ten='Vợ lẽ của {}'.format(husband.ho_ten), gioi_tinh='nu')
    Marriage.objects.create(husband=husband, wife=wife_1, order=1, status='dang_ket_hon')
    Marriage.objects.create(husband=husband, wife=wife_2, order=2, status='dang_ket_hon')
    all_persons.extend([wife_1, wife_2])


def _mark_dead_with_lunar_dates(all_persons):
    dead_batch = []
    for index, person in enumerate(all_persons):
        if index % DEAD_EVERY_NTH == 0:
            person.death_solar = dt.date(2000, 1, 1)
            person.death_lunar_day = (index % 29) + 1
            person.death_lunar_month = (index % 12) + 1
            dead_batch.append(person)
    if dead_batch:
        Person.objects.bulk_update(dead_batch, ['death_solar', 'death_lunar_day', 'death_lunar_month'])


def _mark_one_adopted_child(all_persons):
    """`parent_kind='nuoi'` on a single deep-generation person -- the tree
    renderer and the public surface (which deliberately never publishes
    `parent_kind`, see `selectors/public.py`) both need at least one to exist.
    """
    adopted = next((p for p in all_persons if p.generation and p.generation >= 3), None)
    if adopted is not None:
        adopted.parent_kind = 'nuoi'
        adopted.save(update_fields=['parent_kind'])
