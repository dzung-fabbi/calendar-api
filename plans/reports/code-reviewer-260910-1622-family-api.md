# Code Review — Personal Family API (`/api/gia-pha/v1/family/*`)

Date: 2026-09-10 · Reviewer: code-reviewer · Mode: static (py_compile only; Django suite runs in docker by lead)

## Scope
- 28 files, ~2,460 LOC (source ~1,730 / tests ~1,000). All new files compile (`py_compile` OK).
- Contract: `docs/gia-pha-api-spec.md` §2/§3/§4/§8/§13. Standards: `docs/code-standards.md`.
- Existing clan endpoints untouched (verified: `urls.py` only adds a top block; `views/__init__.py` only re-exports).

## Overall Assessment
Solid. Layering is respected exactly as the standards ask (services = pure dict/graph code, selectors = ORM, views/`family_link_flow` compose). Every write path checks membership against a family-scoped `FamilyGraph` before touching a row; gates run before row creation; fill side-effects are computed from the pre-write graph; the only nested `atomic()` is a deliberate savepoint. No Critical findings. The main risk is a **test gap on cross-user isolation for relation bodies** — the code is correct today, but the invariant that keeps `set_parent_slot(id-only filter)` safe (`require_person`/`graph.has` in every flow) is not pinned by a test.

## Critical
None.

## High

### H1 — Cross-family ids in relation bodies are untested (security regression risk)
- Where: `giapha/tests/test_family_relations_api.py` (only `add-relative` anchor + `PUT self` + `GET detail` test a stranger's id).
- Why: `selectors/family_write.py:36,46,55` filter by `id` only. Safety rests entirely on `views/family_link_flow.py` calling `rules.require_person` / `graph.has` for **every** id before writing. A future edit dropping one check would silently write into another user's tree. Inspection confirms all paths are guarded today (set_parent L25-27, link_spouse L36-37, unlink L51-52, link_child L60-61, add_relative L98, otherParentId only via `candidates ⊂ graph`), but nothing asserts it.
- Fix: one test class building a stranger family, then for each of the 5 endpoints assert 404/`DANGLING_*`, `ok:false`, and that the stranger row is byte-identical afterwards. Include: `set-parent{parentId=stranger}` → `DANGLING_FATHER`; `set-parent{childId=stranger}` → 404; `link-spouse{bId=stranger}` → `DANGLING_SPOUSE`; `unlink-spouse{bId=stranger}` → 404; `link-child{otherParentId=stranger}` → 200 but slot stays null; `PATCH/DELETE/gio-event` on stranger → 404.

## Medium

### M1 — Query-budget goldens for `family_*` not recorded
- Where: `giapha/tests/snapshots/query_budgets.json` has no `family_root|family_person|family_set_parent|family_link_spouse` keys; `QueryBudgetMixin.assert_budget` (`test_query_counts.py:73-77`) will **record and `skipTest`** on first run.
- Why: standards say goldens are recorded and committed with the change; otherwise CI passes vacuously once and the ratchet is unset.
- Fix: run suite twice in docker, commit updated `query_budgets.json` alongside this change.

### M2 — PATCH does a full `save()`; can clobber a concurrent edge write
- Where: `giapha/selectors/family_write.py:24-28` (`apply_draft` → `person.save()`), called from `views/family.py:67`.
- Why: the row was loaded at L62 with `father_id/mother_id` values; a `set-parent`/`link-spouse` fill landing between load and save is overwritten (lost update). Low probability (single user, two devices) but the spec's whole design separates info from edges.
- Fix: `person.save(update_fields=list(draft) + ['updated_at'])`.

### M3 — No cap on persons per family
- Where: `views/family.py:42`, `views/family_link_flow.py:99` (`create_person`) — unbounded.
- Why: every request loads the whole tree (2 queries, all rows into memory). Spec assumes < 500; an abusive or buggy client can grow one family to 10⁵+ rows and make each of its own requests (and DB) slow. No throttle on these endpoints (consistent with project policy, so the cap is the cheap guard).
- Fix: in `create_person` callers, `if graph has ≥ FAMILY_MAX_PERSONS (e.g. 2000): raise FamilyRuleError('FAMILY_FULL')` — zero extra queries since the graph is already loaded.

### M4 — Ignored `otherParentId` gives the client no signal
- Where: `services/family_rules.py:76-77` (`pick_other_parent` returns `None` when requested id is not a candidate), used by `link_child`/`add_relative`.
- Why: spec §4.6 says fill only when the requested id is a candidate — correct — but a wrong/dangling/foreign id is silently dropped; UI thinks the other parent was set. Not a leak (nothing written), just an honesty gap (standards: "honest answers").
- Fix: return a warning `{code:'OTHER_PARENT_IGNORED', otherId}` in the success envelope (`warning` slot already exists), or reject with `DANGLING_*`/`GENDER_MISMATCH` when the id exists but does not fit.

### M5 — Test modules exceed 200 lines
- `test_family_api.py` 284, `test_family_relations_api.py` 284, `test_family_rules.py` 263. Standards apply "under 200" to code files generally; suggest splitting `test_family_api.py` → `test_family_person_crud_api.py` + `test_family_label_autolink_api.py`, and `test_family_relations_api.py` → spouse/child vs set-parent/add-relative. Low effort, improves grep-ability.

## Low
- L1 `services/family_rules.py:92` literal `'mother'` instead of `MOTHER` constant (works, inconsistent).
- L2 `views/family_base.py:22 id_str` duplicates `serializers/family_output.py:23 _id`. Import one.
- L3 `views/family_relations.py:20` `from giapha.views import family_link_flow as flow` imports through the package while `giapha/views/__init__.py` is still executing. Works only because `views/family.py` (imported first, alphabetically) already loaded the submodule. Use `from giapha.views.family_link_flow import ...` like `views/family.py:19`.
- L4 `FamilySpouse` canonical order (`person_a < person_b` by str) is enforced only in code; a row written the other way (admin/shell) would bypass `unique_together` and double-count in `spouses_by_person`. MySQL 5.7 ignores CHECK constraints, so document it or add `Model.clean()`.
- L5 `services/family_graph.py:133` → `person_rules.descendants` raises `PersonValidationError` (not a `FamilyRuleError`) if its iteration cap trips → would surface as 500. Unreachable in practice (visited-set bounds iterations ≤ nodes < cap), note only.
- L6 `views/family.py:89-98` `SELF_ALREADY_SET` is check-then-write without `select_for_update`; two concurrent PUTs can both succeed (last wins). Negligible for a one-user resource.
- L7 `test_query_counts.py`: one blank line before `class ClanListBudgetTests` (E302) after the mixin refactor.
- L8 `PERSON_NOT_FOUND`(404) vs `DANGLING_*`(400) asymmetry: same unknown id yields 404 as `childId`/`aId` but 400 as `parentId`/`bId`. Spec-compatible; document in api-reference so the client does not branch on status.

## Verified OK (per lead's focus list)
1. **Rules §4** — cycle: `parent in descendants(child)` ✓ (`family_rules.py:31`); `set-parent` replaces, `link-child`/`add-relative` refuse via `check_slot_free`/`check_add_relative` ✓; first-spouse fill only when `spouses_of(person)` empty, computed pre-write for both sides ✓ (`family_link_flow.py:38-39`); other-parent fill only when requested∈candidates or exactly one ✓; delete detaches, no cascade, `self_person` SET_NULL + explicit `refresh_from_db` ✓; `selfId` scalar FK ✓.
2. **Security** — `get_person_or_none`, `load_graph`, `person_rows`, `spouse_rows` all filter `family_id` ✓; `set_self` verifies membership before write ✓; gio-event scoped ✓; `initial()` creates Family **after** `super().initial()` (auth+permission+throttle) so anonymous never creates rows ✓; error envelope only exposes ids from the caller's own family ✓; `gioEventId` opaque, max 64 ✓.
3. **Transactions** — every multi-write view wrapped in `transaction.atomic()` (ATOMIC_REQUESTS is off, so this is load-bearing and present) ✓; `auto_link_by_label` savepoint catches only `FamilyRuleError`; all flows raise before any write so in-memory graph stays consistent on rollback ✓; `update_or_create` is internally atomic+`select_for_update` in Django 3.1 → no bare `IntegrityError` path ✓; `Family.get_or_create` race-safe ✓.
4. **Django 3.1 / MySQL 5.7** — migration creates `Family` (no FKs) → `FamilyPerson` (FK family, self-FKs) → `AddField self_person`, `user` → `FamilySpouse`; ordering correct ✓. `BooleanField(null=True)` is the 3.1-recommended form ✓. UUID pk stored char(32), `.values()` returns `uuid.UUID`, DRF `UUIDField` returns `uuid.UUID`, URL converter returns `uuid.UUID` → graph key comparisons are type-consistent; `canonical_pair` uses `str()` ✓. `USE_TZ=True` so `epoch_ms` is correct ✓.
5. **DRF** — `partial=True` suppresses `default=` (gender/deceased) on PATCH ✓; nested `PersonDraftSerializer` inside `AddRelative` gets defaults (root not partial) ✓; no redundant `source=` ✓; `required=False, default=None` legal ✓; `handle_exception` delegates non-rule errors to `super()` so 401/`WWW-Authenticate` preserved ✓; `first_error_message` recurses nested `fields.person.name` ✓.
6. **Layering / size** — services import no ORM ✓; selectors own all queries ✓; `Prefetch` not needed (row dicts) ✓; every source file < 150 lines ✓; no blanket `except` ✓; `fields='__all__'` absent ✓.
7. **Spec §13 checklist** — all 18 items have a test (`test_family_api.py`, `test_family_relations_api.py`, `test_family_rules.py`), incl. no-orphan on second father, sibling without parents, symmetric spouse + unlink, first vs second spouse fill, slot-taken, cycle, delete-grandpa, deceased w/o date, lunar w/o year, day 0 / month 13, formats, string `relationship`, error envelope. Missing only: cross-family bodies (H1), cycle-guard branch in `first_spouse_fill_targets` (`family_rules.py:98`), `unlink-spouse` with unknown id.

## Positive Observations
- `add_relative` gates before `create_person` — the spec's "không đẻ ra người mồ côi" is structural, and tested.
- Fill targets computed from the pre-link graph and applied after — the "first spouse" semantics are exact and race-free within the request.
- `FamilyRuleError` carries HTTP status + envelope; rule code is HTTP-agnostic and unit-tested on `SimpleTestCase`.
- `finalize_draft` derives `solar_death_date` server-side and drops a stale one when lunar fields change — matches §2.4 including the "leap flag must not block the write" fallback.
- `QueryBudgetMixin` extraction is clean; family budgets assert size-independence against a ~380-person tree.
- Docs updated (`api-reference.md` +256, `system-architecture.md`, `codebase-summary.md`).

## Recommended Actions (priority order)
1. Add cross-family isolation tests for all 5 relation endpoints + PATCH/DELETE/gio-event (H1).
2. Record and commit `family_*` budgets in `snapshots/query_budgets.json` (M1).
3. `apply_draft` → `save(update_fields=...)` (M2).
4. Add `FAMILY_MAX_PERSONS` guard using the already-loaded graph (M3).
5. Surface ignored `otherParentId` as a warning (M4).
6. Cosmetic: L1–L3, L7; split oversized test modules (M5).

## Metrics
- Compile: 28/28 OK. Type coverage: n/a (Python, no annotations — consistent with codebase).
- Lint: not run locally (no flake8 config observed); 1 E302 spotted by eye.
- Spec §13 coverage: 18/18 items have tests. Cross-user coverage: 3 of 13 endpoints.

## Unresolved Questions
1. Spec §4.1 says `PARENT_SLOT_TAKEN` = "Muốn thay phải gỡ trước", yet `set-parent` replaces an occupant silently (`family_link_flow.py:21-29`, per lead's instruction). Does the app's `setFather` really overwrite, or does the edit form clear first? If the latter, `set-parent` should also raise `PARENT_SLOT_TAKEN` when `current not in (None, parentId)`.
2. §8.4 leaves "keep vs delete giỗ event" open; implementation keeps (event is client-side). Confirm and state it in api-reference.
3. Should a first spouse linked with `type='divorced'` still trigger the child-fill side effect? Current code: yes.
4. Should `otherParentId` that exists but is not a candidate be a hard error (`GENDER_MISMATCH`/`DANGLING_*`) rather than ignored (M4)?
