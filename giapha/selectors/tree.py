"""DB-facing queries for the `/tree` endpoint and the parent-change
generation hook.

`tree_payload()` is exactly 2 queries -- Person and Marriage -- regardless of
clan size or whether `?root=&depth=` is given: parent edges are derived from
the Person rows already fetched, never a third query. Everything that
requires no ORM (the generation walk, subtree BFS, row shaping) lives in
`services.tree` and is only called from here.
"""

from giapha.models import Marriage, Person
from giapha.selectors.clan import get_clan_or_none
from giapha.selectors.person import clan_edges
from giapha.services.person_rules import descendants
from giapha.services.tree import (
    compute_generations,
    marriage_edges_from_rows,
    node_from_row,
    parent_edges_from_rows,
    subtree_ids,
)

_ROW_FIELDS = (
    'id', 'ho_ten', 'ten_huy', 'gioi_tinh', 'generation', 'branch',
    'is_truong', 'birth_order', 'birth_solar', 'death_solar',
    'death_lunar_day', 'death_lunar_month', 'death_lunar_leap',
    'father_id', 'mother_id', 'parent_kind',
)

RECOMPUTE_BATCH_SIZE = 500


def tree_payload(clan_id, *, max_persons, root_id=None, depth=None):
    """Builds the full `{clan, nodes, edges, truncated}` response body.

    Returns `None` if `root_id` is given but doesn't match any non-deleted
    person in this clan -- the view turns that into a 404.
    """
    queryset = (
        Person.objects.filter(clan_id=clan_id, is_deleted=False)
        .order_by('id')
        .values(*_ROW_FIELDS, 'clan__ten_ho')
    )
    if root_id is None:
        # `?root=` needs the FULL edge set to walk the subtree correctly
        # (bounded separately, see the module docstring); the plain listing
        # doesn't, so bound it at the DB with `LIMIT max_persons + 1` -- one
        # extra row is all `truncated` needs -- instead of materialising an
        # unbounded clan into memory before truncating in Python (M5).
        queryset = queryset[:max_persons + 1]
    rows = list(queryset)
    row_by_id = {row['id']: row for row in rows}

    if root_id is not None and root_id not in row_by_id:
        return None

    # `ten_ho` rides along on the Person query above via the `clan__ten_ho`
    # join -- no extra round trip. Only a clan with zero non-deleted persons
    # (an edge case, not the size-scaling one the ≤3-query budget guards)
    # falls back to a dedicated lookup.
    if rows:
        ten_ho = rows[0]['clan__ten_ho']
    else:
        clan = get_clan_or_none(clan_id)
        ten_ho = clan.ten_ho if clan is not None else None

    if root_id is not None:
        edge_tuples = [(row['id'], row['father_id'], row['mother_id']) for row in rows]
        wanted_ids = subtree_ids(edge_tuples, root_id, depth)
        rows = [row for row in rows if row['id'] in wanted_ids]

    truncated = len(rows) > max_persons
    if truncated:
        rows = rows[:max_persons]

    included_ids = {row['id'] for row in rows}
    nodes = [node_from_row(row) for row in rows]
    parent_edges = parent_edges_from_rows(rows)

    marriage_rows = list(
        Marriage.objects.filter(husband__clan_id=clan_id)
        .values('husband_id', 'wife_id', 'order', 'status')
    )
    marriage_edges = marriage_edges_from_rows(marriage_rows, included_ids)

    return {
        'clan': {'id': clan_id, 'ten_ho': ten_ho},
        'nodes': nodes,
        'edges': parent_edges + marriage_edges,
        'truncated': truncated,
    }


def recompute_descendant_generations(clan_id, person_id, batch_size=RECOMPUTE_BATCH_SIZE):
    """Recompute + persist `generation` for `person_id` and every descendant
    reachable forward from it, using the FULL clan edge graph (a descendant's
    *other* parent can sit outside this subtree, e.g. married in from a
    different line, and still needs to count toward `max(...)+1`).

    Only rows in the subtree are written, in batches of `batch_size` --
    recomputing the whole clan synchronously here would time out when
    someone edits a person near the root. For a full-clan fixup use
    `manage.py recompute_generations`.
    """
    edges = clan_edges(clan_id)
    generations = compute_generations(edges)
    target_ids = {person_id} | descendants(edges, person_id)

    persons = list(
        Person.objects.filter(clan_id=clan_id, id__in=target_ids, is_deleted=False)
        .only('id', 'generation')
    )
    changed = []
    for person in persons:
        new_generation = generations.get(person.id)
        if person.generation != new_generation:
            person.generation = new_generation
            changed.append(person)

    if changed:
        Person.objects.bulk_update(changed, ['generation'], batch_size=batch_size)
    return len(changed)
