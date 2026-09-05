"""Resolve WHO receives a giỗ reminder -- pure, no ORM, no `request`.

`GioFollow` stores only the *deviation* from the default (see
`plans/260905-1053-gia-pha-dong-ho/phase-06-fcm-push-va-nhac-gio.md` -> B):
the default itself -- "a member follows their own direct ancestors" -- is
resolved here at send time from plain edge tuples. Nothing is materialised,
so editing `father`/`mother` in the tree changes the follow set immediately
and no re-sync command is ever needed.

Every function takes the `[(id, father_id, mother_id), ...]` shape that
`selectors.person.clan_edges` / `clan_edges_all` return, so
`tests/test_gio_follow_service.py` runs on `SimpleTestCase` with no database.
Follow resolution is fed the `clan_edges_all` variant on purpose: the walk
must pass THROUGH a soft-deleted ancestor instead of stopping at them (the
people it can report are restricted separately, by the caller's `person_ids`).
"""

from collections import deque


def ancestors(edges, person_id, max_iterations=None):
    """Every person reachable by walking BACKWARD (child -> parent) from
    `person_id`, following father AND mother. Excludes `person_id` itself.

    Both parent links are followed, so "trực hệ" spans the paternal and the
    maternal line alike -- whichever of the two is actually recorded in the
    tree. No gender filter, no `branch` filter, and deliberately no
    descendants and no collaterals: a user who wants those adds them with an
    `enabled=True` override.

    CYCLE PROTECTION IS `visited`, NOT THE COUNTER. `visited` already enqueues
    every node at most once, so the loop pops at most `len(edges) + 1` times
    and the default `max_iterations = 2 * len(edges) + 10` can never fire --
    it is belt-and-braces, kept only because data written through the Django
    admin bypasses the cycle validation. `discard(person_id)` is the part that
    actually matters, and it is what keeps someone recorded as their own
    ancestor out of their own follow set.

    Should the counter ever be reachable (a caller passing a smaller
    `max_iterations`), it fails OPEN: it returns the partial set collected so
    far and never raises, unlike `services.person_rules.descendants`, which
    fails CLOSED because it gates writes. This one feeds a nightly background
    job, where missing a few recipients beats killing the whole run.
    """
    parents_of = {}
    for row_id, father_id, mother_id in edges:
        parents_of[row_id] = [pid for pid in (father_id, mother_id) if pid is not None]

    visited = set()
    queue = deque([person_id])
    if max_iterations is None:
        max_iterations = 2 * len(edges) + 10
    iterations = 0
    while queue and iterations < max_iterations:
        iterations += 1
        current = queue.popleft()
        for parent_id in parents_of.get(current, ()):
            if parent_id not in visited:
                visited.add(parent_id)
                queue.append(parent_id)

    # A cycle through `person_id` (e.g. someone recorded as their own
    # ancestor) would otherwise leave them in their own follow set.
    visited.discard(person_id)
    return visited


def _overrides_by_user(overrides):
    """`{(user_id, person_id): enabled}` regrouped as
    `{user_id: {person_id: enabled}}` -- one pass, so the per-user loop below
    stays O(overrides) instead of re-scanning the whole map per user.
    """
    by_user = {}
    for (user_id, person_id), enabled in overrides.items():
        by_user.setdefault(user_id, {})[person_id] = enabled
    return by_user


def followers_by_person(edges, bindings, overrides, person_ids):
    """`{person_id: {user_id, ...}}` -- who should be told about each giỗ.

    - `bindings`  : `{user_id: self_person_id}`, only members who answered
      "I am this node in the tree". A member with no binding has no direct
      line and therefore no default follows -- only what they added by hand.
      Guessing on their behalf would be worse than silence.
    - `overrides` : `{(user_id, person_id): enabled}` from `GioFollow`.
    - `person_ids`: the persons whose giỗ is actually due; everything is
      intersected with it, INCLUDING `enabled=True` overrides, so a manual
      follow can never pull in someone outside this clan/run.

    Persons with no follower are omitted rather than mapped to an empty set,
    so the caller can iterate the result directly.
    """
    person_ids = set(person_ids)
    overrides_by_user = _overrides_by_user(overrides)

    followers = {}
    # Two members can bind to the same node only in different clans, but the
    # cache also pays off when this is called per clan in a long loop.
    ancestors_cache = {}
    for user_id in set(bindings) | set(overrides_by_user):
        self_person_id = bindings.get(user_id)
        if self_person_id is None:
            followed = set()
        else:
            if self_person_id not in ancestors_cache:
                ancestors_cache[self_person_id] = ancestors(edges, self_person_id)
            followed = ancestors_cache[self_person_id] & person_ids

        for person_id, enabled in overrides_by_user.get(user_id, {}).items():
            if enabled:
                if person_id in person_ids:
                    followed.add(person_id)
            else:
                followed.discard(person_id)

        for person_id in followed:
            followers.setdefault(person_id, set()).add(user_id)
    return followers
