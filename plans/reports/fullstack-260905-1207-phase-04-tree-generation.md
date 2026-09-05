# Phase 4 Implementation Report -- Tree endpoint, generation, search/filter

Plan: `plans/260905-1053-gia-pha-dong-ho/phase-04-tree-endpoint-va-generation.md`

## Files created
- `giapha/services/tree.py` (182 lines) -- pure: `compute_generations(edges)` (Kahn-style topological BFS, cycle-safe fallback), `subtree_ids(edges, root_id, depth)`, `node_from_row`, `parent_edges_from_rows`, `marriage_edges_from_rows`
- `giapha/selectors/tree.py` (114 lines) -- `tree_payload(clan_id, *, max_persons, root_id, depth)` (2 queries: Person `.values()` incl. `clan__ten_ho` join, Marriage `.values()`), `recompute_descendant_generations(clan_id, person_id)`
- `giapha/serializers/tree.py` (49 lines) -- `TreeSerializer`/`TreeClanSerializer`/`TreeNodeSerializer`/`TreeEdgeSerializer` (edge is a passthrough given heterogeneous parent/marriage shape)
- `giapha/views/tree.py` (56 lines) -- `ClanTreeAPIView`, `IsClanMember`, `?root=&depth=` int validation
- `giapha/views/person_list.py` (139 lines, new) -- `PersonListCreateAPIView` split out of `views/person.py` to stay <200 lines after adding search/filter
- `giapha/management/commands/recompute_generations.py` (74 lines) -- `<clan_id>` or `--all`, `bulk_update(batch_size=500)`
- `giapha/tests/test_tree_service.py` (169 lines, SimpleTestCase, no DB -- confirmed via "Skipping setup of unused database(s)" in test output)
- `giapha/tests/test_tree_api.py` (328 lines, TestCase, real MySQL)

## Files modified
- `giapha/views/person.py` -- now only `PersonDetailAPIView`; PATCH detects `father_id`/`mother_id` change, calls `recompute_descendant_generations` inside the same transaction, `refresh_from_db(['generation'])` before serializing (own generation may have just changed)
- `giapha/selectors/person.py` -- added `search_persons(clan_id, *, q, generation, branch, death_year)`, reuses `persons_of`
- `giapha/urls.py` -- added `clans/<clan_id>/tree` route; import list updated
- `giapha/views/__init__.py`, `giapha/selectors/__init__.py`, `giapha/serializers/__init__.py` -- re-exports for new symbols

## Deviations from file list (flagged, not hidden)
- Split `views/person.py` into `views/person.py` + `views/person_list.py` (not in the given "Modify" list) -- required to keep both under 200 lines once search/filter + `LimitOffsetPagination` landed in the list view. Mirrors the existing `person.py`/`person_revision.py` split precedent in this codebase.
- Touched `selectors/person.py` for `search_persons` -- not in the given file list, but `?q=&generation=&branch=&death_year=` has nowhere else to live per the selectors-own-queries rule.

## Key design decisions
- **`generation` algorithm**: implemented as Kahn-style topological propagation (pending-parent-count per node) rather than naive BFS-first-arrival, so "both parents known, different generations" resolves correctly regardless of visit order (`max(gen_father, gen_mother)+1`). A `2*len(edges)+10` iteration cap sits on top as defense-in-depth (matches `services.person_rules.descendants` convention); nodes that never resolve (mid-cycle, or depending on one) fall back to generation 1 instead of hanging.
- **Query budget**: `IsClanMember` (1, cached) + Person `.values()` (1) + Marriage `.values()` (1) = 3 total, verified via `assertNumQueries(3)` for plain tree, tree with 20 extra persons, and tree with `?root=&depth=` -- all exactly 3. `ten_ho` rides the Person query via `clan__ten_ho` join (no extra round trip); only a zero-person clan falls back to one extra `get_clan_or_none` call (documented, doesn't scale with size).
- **Truncation**: no separate `.count()` query -- fetch once, `len(rows) > MAX_CLAN_PERSONS` decides `truncated`, then slice. Verified with `@override_settings(MAX_CLAN_PERSONS=2)`.
- **Recompute-on-parent-change**: computes `compute_generations` over the FULL clan edge graph (a descendant's *other* parent can sit outside the subtree, e.g. married in) but only persists `{person_id} ∪ descendants(edges, person_id)` via `bulk_update(batch_size=500)` -- verified with a cross-branch reassignment test where the moved node's own generation shifts by more than 1.
- **Pagination**: switched `PersonListCreateAPIView` from `PageNumberPagination` to `LimitOffsetPagination(default_limit=50, max_limit=200)` per spec; existing `test_person_api.py::test_list_is_paginated` only asserts `count`/`next` keys exist, unaffected.
- **`generation` NOT auto-set on create**: `PersonWriteSerializer` already allows clients to set `generation` directly on create (phase 3 decision -- manual gia phả entry). Phase 4 spec's modify-list only calls out the PATCH path ("sau khi đổi cha/mẹ thì gọi tính lại generation nhánh con"), so create was left untouched -- YAGNI, and changing it would be an undocumented behavior change to existing phase-3 API contract.

## Tests status
- `test_tree_service.py`: 23/23 pass, confirmed 0 DB queries (Django skips test DB setup for the module)
- `test_tree_api.py`: 28/28 pass (query budget x3, tree shape, soft-delete exclusion, root/depth, truncation, search/filter x7, recompute-on-patch x3, management command x4)
- Full `giapha` suite: 169/169 pass
- Full project suite: 219/219 pass (168 baseline + 51 new -- no regressions)
- `makemigrations giapha apis --check --dry-run`: no changes detected
- `grep -rn "from apis\|import apis" giapha/`: empty

## Unresolved questions
- None blocking. One judgment call to flag: response envelope for `/tree` is the raw `{clan, nodes, edges, truncated}` shape per the spec's literal example, NOT wrapped in `{'data': ...}` like every other giapha endpoint -- intentional, following "follow the exact JSON shape" instruction over house convention.

**Status:** DONE
**Summary:** Tree endpoint (≤3 queries), cycle-safe topological generation algorithm, subtree root/depth filter, person search/filter (q on ho_ten+ten_huy, generation/branch/death_year), descendant-subtree recompute hook on parent change, and `recompute_generations` command all implemented and tested; full suite 219/219 green, no migration drift, no `apis` imports.
**Concerns/Blockers:** None.
