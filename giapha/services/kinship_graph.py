"""The graph half of the xưng-hô calculator: walking up to a common ancestor.

Pure -- takes the `selectors.person.clan_kinship_rows` dict rows and nothing
else. Split from `services/kinship.py` so the traversal and the vocabulary
are two separate things to get right.

FAIL-OPEN, DELIBERATELY
-----------------------
`ancestor_index`'s safety counter returns what it has instead of raising,
unlike `person_rules.descendants`, which fails CLOSED because it gates
writes, and like `gio_follow.ancestors`, which fails open because it feeds a
background job. Neither reason applies here, so the choice is made on its own
merits: this is a read and a 500 helps nobody.

THE COUNTER IS A BACKSTOP, NOT A SAFETY GUARANTEE. An earlier version of this
docstring claimed a truncated walk "can only MISS a common ancestor, never
invent a nearer one, so the worst outcome is `term: null`". That is false.
BFS does discover ancestors in non-decreasing depth order, but if truncation
drops the NEAREST common ancestor, `best_common_ancestor` picks a surviving
farther one, whose depth pair gives a different `gap` -- a confidently WRONG
term, not a null. Two frontier nodes at the same depth are popped separately,
so a same-depth split is reachable in principle.

What makes it safe is that the counter cannot fire at all: `index` admits
each person at most once, so the loop pops at most `len(rows) + 1` times
against a budget of `2 * len(rows) + 10`. It is kept because Django admin
writes bypass `person_rules.validate_no_cycle`, so a parent cycle can already
be in the table -- and `parent_id in index` is what actually makes such data
terminate rather than hang. Callers passing an explicit `max_iterations`
(only the tests do) opt out of that argument and own the consequence.
"""

from collections import deque

from giapha.services.kinship_terms import NGOAI, NOI


def ancestor_index(rows, person_id, max_iterations=None):
    """`{ancestor_id: (depth, side, via)}` for `person_id` and everyone above.

    `person_id` itself is included at `(0, None, None)`. Direct-line answers
    ("B is A's grandfather") depend on that: there the common ancestor IS one
    of the two people.

    - `depth`: generations up from `person_id`, shortest path (BFS).
    - `side` : `NOI` if the FIRST step up was `father`, `NGOAI` if `mother`,
      then inherited -- the father's mother is still bên nội.
    - `via`  : that ancestor's own child on the path back down toward
      `person_id`. This answers "which of the ancestor's children is A's
      branch?", which is the pair `birth_order` is compared on.

    A person absent from `rows` simply has no parents here and the walk stops
    at them, so an id from another clan yields `{id: (0, None, None)}` rather
    than an exception.
    """
    parents_of = {}
    for row in rows:
        parents_of[row['id']] = (row['father_id'], row['mother_id'])

    index = {person_id: (0, None, None)}
    queue = deque([person_id])
    if max_iterations is None:
        max_iterations = 2 * len(rows) + 10
    iterations = 0
    while queue and iterations < max_iterations:
        iterations += 1
        current = queue.popleft()
        depth, side, _via = index[current]
        father_id, mother_id = parents_of.get(current, (None, None))
        for parent_id, step_side in ((father_id, NOI), (mother_id, NGOAI)):
            # `parent_id in index` is the cycle guard AND the shortest-path
            # guard: the first (shallowest) arrival wins and is never
            # overwritten, so a loop back onto `person_id` cannot move them
            # off depth 0.
            if parent_id is None or parent_id in index:
                continue
            index[parent_id] = (depth + 1, side or step_side, current)
            queue.append(parent_id)
    return index


def best_common_ancestor(index_a, index_b):
    """`(ancestor_id, depth_a, depth_b, side_from_a)` for the nearest shared
    ancestor of two `ancestor_index` results, or `None` when there is none.

    Nearest = smallest `depth_a + depth_b`; ties broken by the smaller
    `depth_a`, then by id, so a clan where two ancestors are equally near
    always renders the same one instead of following dict order.
    """
    best_key = None
    best = None
    for ancestor_id, (depth_a, side, _via) in index_a.items():
        entry_b = index_b.get(ancestor_id)
        if entry_b is None:
            continue
        key = (depth_a + entry_b[0], depth_a, ancestor_id)
        if best_key is None or key < best_key:
            best_key = key
            best = (ancestor_id, depth_a, entry_b[0], side)
    return best


def lowest_common_ancestor(rows, a_id, b_id):
    """`(ancestor_id, depth_a, depth_b, side)` or `None` -- the convenience
    form for callers that do not need the indexes afterwards.
    """
    return best_common_ancestor(ancestor_index(rows, a_id), ancestor_index(rows, b_id))
