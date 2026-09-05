# Phase Implementation Report

### Executed Phase
- Phase: phase-03-person-marriage-crud-va-validation
- Plan: C:\Users\vdong\Projects\calendar-api\plans\260905-1053-gia-pha-dong-ho\
- Status: completed

### Files Modified
Created:
- `giapha/selectors/person.py` (76 lines) -- `clan_edges`, `birth_solar_by_id`, `get_person_or_none`, `get_person_any`, `persons_of`, `active_person_count`, `children_count`
- `giapha/selectors/marriage.py` (35 lines) -- `get_marriage_or_none`, `marriages_of`, `orders_for_husband`, `next_order_for_husband`
- `giapha/services/person_rules.py` (189 lines) -- pure validators + `descendants`/`validate_person_write` orchestrator
- `giapha/services/revision.py` (60 lines) -- `snapshot`, `record`, `restore`
- `giapha/serializers/person.py` (74 lines) -- `PersonWriteSerializer`, `PersonReadSerializer`, `PersonRevisionSerializer`
- `giapha/serializers/marriage.py` (28 lines) -- `MarriageSerializer`
- `giapha/views/person.py` (195 lines) -- list/create (incl. bulk), detail/patch/soft-delete
- `giapha/views/person_revision.py` (63 lines, split out to keep person.py <200) -- revisions list + restore
- `giapha/views/marriage.py` (104 lines) -- list/create/patch/delete
- `giapha/tests/test_person_rules.py` (273 lines, SimpleTestCase, no DB)
- `giapha/tests/test_person_api.py` (329 lines)
- `giapha/tests/test_marriage_api.py` (107 lines, not in spec's file list, added for Marriage endpoint coverage)

Modified:
- `giapha/urls.py` -- added person/marriage/revision/restore routes
- `giapha/selectors/__init__.py`, `giapha/serializers/__init__.py`, `giapha/views/__init__.py` -- flat re-exports
- `giapha/tests/factories.py` -- added `build_person()` helper

### Tasks Completed
- [x] `no_cycle` via `descendants()` BFS + safety counter (`2*len(edges)+10`); tested with direct + indirect A->B->C->A cycle + pre-existing self-loop/corrupt data
- [x] `parent_in_same_clan` -- membership check against `ids_from_edges(clan_edges(...))`, no separate query
- [x] `parent_born_before_child` 12y gap + `force=true`, owner-only (403 for editor), enforced via `_wants_force()` reading cached role
- [x] `death_after_birth`, `lunar_death_valid`, `death_pair_complete`, `self_not_parent`, `clan_size_cap`, `marriage_distinct`, `marriage_order_unique` -- all in `person_rules.py`, each with passing + violating unit test
- [x] Bulk create: `clan_edges`/`birth_solar_by_id`/`active_person_count` loaded once, mutated in-memory per record; capped at 200; whole batch in one `transaction.atomic()` (one bad row rolls back all)
- [x] Soft delete consistency: every selector filters `is_deleted=False` except `get_person_any` (revisions/restore, deliberately)
- [x] Delete blocked when person is father/mother of any child; 400 names the count
- [x] Revision snapshot taken before mutation, excludes id/created_at/updated_at, `json.dumps`'d
- [x] Restore re-applies snapshot after recording current state as a new revision first (never one-way)
- [x] Marriage `order` defaults to `max(existing)+1`; uniqueness enforced per husband
- [x] All writes in `transaction.atomic`
- [x] `PersonWriteSerializer`/`PersonReadSerializer` split per spec (phase 9 hook)

### Tests Status
- Type check: N/A (no mypy configured in repo)
- Unit tests: pass -- `giapha` suite 118/118 (up from 34), full suite 168/168 (up from 84), no regressions
- `makemigrations giapha --check --dry-run` -> "No changes detected"
- `test_person_rules.py` confirmed `SimpleTestCase`-only, no DB fixtures/queries anywhere in the file

### Issues Encountered
- Two test files exceed 200 lines (`test_person_rules.py` 273, `test_person_api.py` 329). Deliberate: spec's acceptance criteria explicitly name `test_person_rules.py` as a single file, and splitting many small independent `assertRaises`/happy-path test methods loses readability for little gain. Production code files are all <200 lines.
- `MarriageSerializer` accepts `husband_id`/`wife_id` as writable fields (needed for create), but `PATCH` only ever applies `order`/`status`/`note` -- husband/wife are treated as immutable after creation (documented in a view docstring). Delete+recreate is the intended fix path for a wrong partner.
- Restore does not re-run `person_rules` validation against the CURRENT tree state -- it applies the snapshot verbatim (per spec: "trả đúng dữ liệu trước đó"). If the tree changed enough between snapshot and restore that the old values are now invalid (e.g. a since-deleted grandparent), restore will silently reintroduce a stale reference. Acceptable for this phase; flagged for awareness.
- Pagination has no prior pattern in the codebase (apis/giapha use plain `APIView`, no `pagination_class` anywhere) -- built a local `PersonPagination(PageNumberPagination)` and wired it manually inside `PersonListCreateAPIView.get`, wrapping the existing `{'data': ...}` envelope with `count`/`next`/`previous` siblings.

### Next Steps
- Phase 4 can consume `selectors.person.clan_edges(clan_id)` directly -- signature unchanged: `[(id, father_id, mother_id), ...]`.
- Phase 9's public Person serializer can subclass `PersonReadSerializer` without inheriting write-path fields.
- No new migration was needed; `Person`/`Marriage`/`PersonRevision` models from phase 2 were used as-is.

### Unresolved Questions
- Should restore re-validate against current tree state (reject restoring a now-invalid snapshot) rather than applying verbatim? Left as verbatim-apply per spec wording; flag if phase 4/7 hit corrupt-tree issues traceable to a stale restore.
- Bulk create's `force=true` applies to the WHOLE batch uniformly. If a future need arises for per-record force flags, the payload shape would need to change (currently a flat list of person dicts, no per-item control field).

**Status:** DONE
**Summary:** Person+Marriage CRUD, full validation rule set (person_rules.py, pure/no-DB), and revision/restore shipped; 118 giapha tests (84 new) pass, full suite 168/168, no migration needed.
**Concerns/Blockers:** None blocking. See unresolved questions above (restore verbatim-apply, force flag scope).
