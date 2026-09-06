"""Pure tree-shaping helpers for the `/tree` endpoint and generation walk.

No ORM, no Django model imports, no `request` -- every function here takes
plain tuples/dicts (the same `[(id, father_id, mother_id), ...]` shape as
`selectors.person.clan_edges`, or `.values()` row dicts), so
`tests/test_tree_service.py` runs on `SimpleTestCase` with no database.

`compute_generations` and `subtree_ids` share the children-map/safety-counter
shape of `services.person_rules.descendants` for the same reason that module
documents: data entered through Django admin bypasses API validation and can
already contain a parent-child cycle, so both walks must terminate instead of
hanging on it.
"""

from collections import deque

# The exact `nodes[]` entry shape returned by `node_from_row` below. This is
# now the ONE place the `/tree` node shape is declared -- `serializers.tree.
# TreeNodeSerializer` is a passthrough (no per-field declarations) precisely
# because that endpoint requires `IsClanMember` auth, so there is no
# whitelist-safety reason to re-declare fields there. `tests/test_tree_
# service.py` asserts `node_from_row(...).keys() == set(NODE_FIELDS)` for both
# a living and a dead row, which is what used to be guaranteed implicitly by
# the serializer's field list.
NODE_FIELDS = (
    'id', 'ho_ten', 'ten_huy', 'gioi_tinh', 'generation', 'branch', 'is_truong',
    'birth_order', 'is_living', 'birth_year', 'death_year', 'death_lunar', 'has_photo',
)


def _children_of(edges):
    """`{parent_id: {child_id, ...}}` built from `edges`, considering both
    the father and the mother side of each row.
    """
    children_of = {}
    for person_id, father_id, mother_id in edges:
        if father_id is not None:
            children_of.setdefault(father_id, set()).add(person_id)
        if mother_id is not None:
            children_of.setdefault(mother_id, set()).add(person_id)
    return children_of


def compute_generations(edges):
    """`edges`: `[(id, father_id, mother_id), ...]`. Returns `{id: generation}`.

    Roots (neither parent known -- including a parent id that doesn't
    resolve to anyone in `edges`, e.g. a dangling reference from corrupt
    data) start at 1. A child inherits `max` over its *known* parents'
    generations, plus 1 -- one parent known behaves the same as `max` over a
    single value. Uses Kahn-style topological propagation (each id is only
    finalized once every known parent already has a generation), which
    handles the "both parents known but at different generations" case
    correctly regardless of BFS visit order.

    A pre-existing cycle (or a node depending on one) never reaches a
    resolvable state and is left out of the topological pass; the final
    loop assigns it `1` as a safe fallback instead of leaving it unset. The
    `2 * len(edges) + 10` iteration cap is defense-in-depth on top of that --
    the propagation is already bounded by construction (each id is enqueued
    at most once), mirroring the safety-counter convention in
    `services.person_rules.descendants`.
    """
    ids = {row[0] for row in edges}
    known_parents = {}
    pending = {}
    children_of = {}
    for person_id, father_id, mother_id in edges:
        parents = [pid for pid in (father_id, mother_id) if pid is not None and pid in ids]
        known_parents[person_id] = parents
        pending[person_id] = len(parents)
        for pid in parents:
            children_of.setdefault(pid, []).append(person_id)

    generations = {}
    queue = deque(person_id for person_id, count in pending.items() if count == 0)
    for person_id in queue:
        generations[person_id] = 1

    max_iterations = 2 * len(edges) + 10
    iterations = 0
    while queue and iterations < max_iterations:
        iterations += 1
        current = queue.popleft()
        for child_id in children_of.get(current, ()):
            pending[child_id] -= 1
            if pending[child_id] == 0:
                parents = known_parents[child_id]
                generations[child_id] = (
                    max(generations[pid] for pid in parents) + 1 if parents else 1
                )
                queue.append(child_id)

    for person_id in ids:
        generations.setdefault(person_id, 1)
    return generations


def subtree_ids(edges, root_id, depth=None):
    """IDs reachable downward from `root_id`, including `root_id` itself --
    "cây con từ một người" always includes the person clicked. `depth`
    caps how many levels of children to include (`depth=1` => root plus its
    direct children only); `None` means unlimited.
    """
    children_of = _children_of(edges)

    visited = {root_id}
    frontier = {root_id}
    max_iterations = 2 * len(edges) + 10
    iterations = 0
    level = 0
    while frontier and iterations < max_iterations and (depth is None or level < depth):
        next_frontier = set()
        for current in frontier:
            iterations += 1
            for child_id in children_of.get(current, ()):
                if child_id not in visited:
                    visited.add(child_id)
                    next_frontier.add(child_id)
        frontier = next_frontier
        level += 1
    return visited


def node_from_row(row):
    """One `nodes[]` entry from a Person `.values()` row. Deliberately lean
    (id/name/generation/branch/dates) -- `tieu_su`, `que_quan` and mộ phần
    fields are NOT here, they come from `GET /persons/{pid}` on demand.
    """
    birth_solar = row['birth_solar']
    death_solar = row['death_solar']
    death_lunar_day = row['death_lunar_day']
    death_lunar_month = row['death_lunar_month']
    has_death_info = death_solar is not None or death_lunar_day is not None or death_lunar_month is not None

    return {
        'id': row['id'],
        'ho_ten': row['ho_ten'],
        'ten_huy': row['ten_huy'],
        'gioi_tinh': row['gioi_tinh'],
        'generation': row['generation'],
        'branch': row['branch'],
        'is_truong': row['is_truong'],
        'birth_order': row['birth_order'],
        'is_living': not has_death_info,
        'birth_year': birth_solar.year if birth_solar is not None else None,
        'death_year': death_solar.year if death_solar is not None else None,
        'death_lunar': (
            {'day': death_lunar_day, 'month': death_lunar_month, 'leap': row['death_lunar_leap']}
            if death_lunar_day is not None and death_lunar_month is not None
            else None
        ),
        # `/tree` NEVER mints a presigned URL (phase 8 spec). NOT because it
        # would be a network request -- `generate_presigned_url` is a local
        # HMAC computation, no socket involved, ~0.3ms -- but because it's
        # still ~0.3ms of CPU plus ~500 bytes of payload for EVERY node on
        # EVERY tree load, for a URL most nodes on a large tree won't be
        # looked at. Worse, a presigned GET's 1-hour TTL starts counting
        # down the moment it's minted, not when the client actually uses it
        # -- pre-generating one per node on tree load means most of that
        # hour is spent before anyone scrolls to that person, so by the
        # time a client wants the photo, a meaningful fraction of nodes
        # would already need a fresh URL anyway. Only a bool rides along;
        # the real URL comes from `GET /persons/{pid}` or the batched
        # `POST /photo-urls` when the client actually needs it, minted at
        # the moment it's needed.
        'has_photo': bool(row['photo_key']),
    }


def parent_edges_from_rows(rows):
    """`edges[]` entries of `type: parent` for every row whose father/mother
    is also present in `rows` -- a parent outside the given rows (truncated
    out, or above a `?root=` subtree) is silently omitted rather than
    pointing at a node the client never received.
    """
    included_ids = {row['id'] for row in rows}
    edges = []
    for row in rows:
        child_id = row['id']
        father_id = row['father_id']
        mother_id = row['mother_id']
        if father_id is not None and father_id in included_ids:
            edges.append({
                'type': 'parent', 'from': father_id, 'to': child_id,
                'role': 'father', 'kind': row['parent_kind'],
            })
        if mother_id is not None and mother_id in included_ids:
            edges.append({
                'type': 'parent', 'from': mother_id, 'to': child_id,
                'role': 'mother', 'kind': row['parent_kind'],
            })
    return edges


def marriage_edges_from_rows(marriage_rows, included_ids):
    """`edges[]` entries of `type: marriage` for every marriage whose both
    partners are in `included_ids` -- same truncation/subtree reasoning as
    `parent_edges_from_rows`.
    """
    return [
        {
            'type': 'marriage', 'a': row['husband_id'], 'b': row['wife_id'],
            'order': row['order'], 'status': row['status'],
        }
        for row in marriage_rows
        if row['husband_id'] in included_ids and row['wife_id'] in included_ids
    ]
