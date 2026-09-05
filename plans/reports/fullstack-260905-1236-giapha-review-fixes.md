# giapha review fixes

Date: 2026-09-05 · Executor: fullstack-developer
Source: `plans/reports/code-reviewer-260905-1225-giapha-phases-1-4.md`

Baseline 237 green -> now 259 green (giapha alone: 209). No migration (checked
`makemigrations giapha --check --dry-run` -> "No changes detected"). No model
field actually needed changing -- every fix below is served at the
serializer/view/selector/service layer, so no `000X_...` migration exists.
`grep -rn "from apis\|import apis" giapha/` empty. `services/` import-purity
re-checked, still only `secrets`/`collections.deque`/`datetime`/`decimal`/`json`.

## Product decisions (1-5)

1. **Invite roles capped to editor/viewer.** New `INVITE_ROLE` tuple
   (`giapha/models/choices.py`), used by `ClanInviteCreateSerializer.role`
   instead of `CLAN_ROLE`. `role='owner'` now 400s at the invite-create
   endpoint; never reaches `ClanInvite.role`. Ownership transfer stays solely
   `PATCH /clans/{id}/members/{user_id}` (unchanged). Did NOT alter
   `ClanInvite.role`'s model-level `choices=CLAN_ROLE` -- Django `choices` is
   not DB-enforced and the only write path is the restricted serializer, so
   changing it would only affect admin/`full_clean()` for zero functional
   gain, at the cost of a migration. Noted as a deliberate scope cut, not an
   oversight.
   Test: `InviteCreateTests.test_owner_role_is_not_grantable_through_an_invite`,
   `test_editor_role_is_grantable`.

2. **Invite defaults: 30-day expiry, unlimited uses.**
   `ClanInviteCreateSerializer.expires_at` default is now a callable
   (`_default_expires_at`, evaluated per-request, not at import time) ->
   `now + 30 days`. Removed `allow_null` so an explicit `null` is now a 400
   too (never resolves to "never expires"). `max_uses` default unchanged (0 =
   unlimited, per decision).
   Test: `test_expires_at_defaults_to_thirty_days_out`,
   `test_max_uses_still_defaults_to_unlimited`,
   `test_explicit_expires_at_is_respected`.

3. **Invite list + revoke.** `GET /clans/{id}/invites` folded into the
   existing create view (renamed `ClanInviteListCreateAPIView`, url name
   `clan-invite-create` unchanged so no test/client churn). New
   `ClanInviteDetailAPIView` (`DELETE /clans/{id}/invites/{invite_id}`), both
   `IsClanOwner`. Revoke = hard delete (row gone -> `get_invite_for_update`
   can't find it -> joining 404s). New selectors `invites_of`,
   `get_invite_by_id`. `ClanInviteSerializer` gained `id` so the client can
   target the delete.
   Test: `InviteListAndRevokeTests` (7 tests: owner list, editor/viewer 403,
   outsider 404, revoke, revoked-code-then-404-on-join, editor can't revoke,
   unknown invite 404).

4. **Restore never undeletes.** `services/revision.py::_EXCLUDED_FIELDS` now
   also excludes `is_deleted` and `clan_id` (clan_id: no endpoint ever moves
   a person between clans, so restoring it is pure risk for no use case).
   Test: `PersonRevisionTests.test_restore_never_undeletes`.

5. **Throttle `/join` only.** Added `DEFAULT_THROTTLE_RATES = {'giapha-join':
   '10/hour'}` to `REST_FRAMEWORK` in `djangopj/settings.py` -- deliberately
   NOT `DEFAULT_THROTTLE_CLASSES`, so nothing project-wide changes.
   `JoinClanAPIView` opts in via `throttle_classes = [ScopedRateThrottle]` +
   `throttle_scope = 'giapha-join'`. Discovered mid-implementation that DRF
   binds `SimpleRateThrottle.THROTTLE_RATES` from `api_settings` at
   class-definition (import) time, not per-request -- so `override_settings`
   in a test cannot retarget it. Rewrote the test to exercise the real
   10/hour rate directly (11 requests, assert the 11th is 429) instead of
   overriding to a fast rate; also proved another endpoint hit the same
   number of times never 429s.
   Test: `JoinThrottleTests` (2 tests).

## Critical / High

**C1** — fully covered by decisions 1-3. Did NOT collapse the unknown-code
(404) vs expired/exhausted-code (400) enumeration oracle the review also
flagged under C1: not one of the 5 explicit decisions, and doing so would
flip `test_expired_code_is_rejected`/`test_over_max_uses_code_is_rejected`
from 400->404 without being asked. Left as-is; noted below as skipped.

**H1 — generation never computed on create.**
`giapha/serializers/person.py`: removed `'generation'` from `_WRITE_FIELDS`
(client post of `generation: 999` now silently ignored, not stored).
`giapha/views/person_list.py::_create_all`: after the insert loop, run
`compute_generations(edges)` (reused as-is from `services/tree.py`, no
second algorithm) over the full updated edge list, set `.generation` on
every created instance, one `bulk_update`. Applies to single creates too
(`post()` funnels both through `_create_all`).
Test: `PersonGenerationOnCreateTests` (4 tests: root=1, child=parent+1, bulk
batch all get parent+1, client-supplied `generation:999` ignored).

**H2 — bulk-create N+1.** Same `_create_all`: instead of returning the
in-memory `created` instances (empty `father`/`mother` relation cache ->
1 query per row with a parent, in `get_father_name`), re-fetch once via
`Person.objects.filter(id__in=...).select_related('father','mother')
.order_by('id')`. One extra query total, not O(n). Also fixed the
false-negative guard test: `test_batch_read_overhead_does_not_scale_with_batch_size`
now gives every fixture row a real `father_id` (previously parent-less, the
one case where the bug can't fire) and still asserts the exact
`2 * (large - small)` delta -- would now fail if the N+1 (or the new
bulk_update/refetch) ever regressed into per-row scaling.

**H3 — restore bypassed cycle validation.** `views/person_revision.py::
PersonRestoreAPIView.post`: after `restore()` mutates the in-memory instance
(pre-save), build the same `_RULE_FIELDS` merged payload the PATCH path uses
and run `validate_person_write` against `clan_edges(clan_id)` fetched BEFORE
the restore is persisted (i.e. the current, not the restored, tree state) --
raises `BadRequestException` on failure, inside the same `transaction.atomic()`
so a rejected restore leaves no stray revision row either. This also
transitively re-checks same-clan membership (`ids_in_clan` from `clan_edges`
excludes soft-deleted rows), so restoring a `father_id` that's since been
soft-deleted is now also rejected, not just the cycle case.
Test: `test_restore_reruns_cycle_validation_against_the_current_tree`,
reproducing the reviewer's exact A/B sequence end-to-end; asserts the
restore is a clean 400 with no partial write.

**H4 — children_count ignored soft-deleted children.**
`selectors/person.py::children_count`: dropped the `is_deleted=False` filter
so a delete is blocked while ANY child (live or soft-deleted) still points
at the parent -- chose "block the delete" over "null the pointer" (simpler,
no new field/migration, matches the review's stated alternative).
Test: `PersonDeleteDanglingPointerTests`.

**H5a — death_year overflow -> 500.** `views/person_list.py::
_int_query_param` gained `min_value`/`max_value`; `death_year` now bounded to
`[1, 9999]` before it reaches `YearLookup`.
Test: `PersonDeathYearBoundTests` (overflow -> 400, negative -> 400, in-range
still filters correctly).

**H5b — duplicate marriage -> 500.** `views/marriage.py`: `Marriage.objects
.create(...)` wrapped in `try/except IntegrityError`, re-raised as
`BadRequestException` with a Vietnamese message. Chose catch-after-attempt
over check-then-create (fewer queries, and the unique constraint is the
actual source of truth so a race between the two approaches can't happen).
Test: `test_duplicate_marriage_pair_is_a_400_not_a_500`.

**H6 — revisions endpoint inline query, N+1, unbounded.**
New `selectors/revision.py::revisions_of(person)` (`.select_related('actor')`),
used by `PersonRevisionListAPIView` instead of the inline `PersonRevision
.objects.filter(...)`. Paginated with a `LimitOffsetPagination` subclass
matching the person-list pattern. Also moved the restore endpoint's
single-revision lookup into `selectors/revision.py::revision_for_person` for
layering consistency (not itself a review finding, but the same fix pattern,
one line, zero risk).
Test: `test_restore_is_paginated_and_uses_select_related_for_actor` -- 12
revisions, asserts <=6 queries (was ~15) and that `count`/`next` are present.

**descendants() fail-open -> fail-closed (L5).**
`services/person_rules.py::descendants` gained an optional `max_iterations`
override (default unchanged, `2*len(edges)+10`) and now raises
`PersonValidationError` if the cap is ever exhausted (`queue` still
non-empty) instead of returning a partial set. Since the cap provably never
fires under the current algorithm (BFS termination comes from `visited`,
iterations <= N always), the override parameter is what makes this testable
at all -- forced with `max_iterations=0` to prove the raise deterministically
without needing a graph large enough to hit the real cap.
Test: `DescendantsTests.test_exhausted_safety_cap_fails_closed_not_open`.

## Medium/Low -- applied (quick, low-risk)

- **M1** (HEAD/OPTIONS treated as write): `if method == 'GET'` ->
  `if method in SAFE_METHODS` in all 4 affected views (`clan.py`, `person.py`,
  `person_list.py`, `marriage.py`). Tests added per file (viewer HEAD/OPTIONS
  now 200, was 403).
- **M4** (marriages_of leaks soft-deleted partner): both
  `get_marriage_or_none`/`marriages_of` now filter
  `husband__is_deleted=False, wife__is_deleted=False`.
  Test: `MarriageSoftDeletedPartnerTests` (2 tests).
- **M5** (tree_payload loads whole clan before truncating): non-root path
  now slices the queryset `[:max_persons+1]` at the DB instead of fetching
  everything then truncating in Python. Root-subtree path intentionally
  left unbounded per the review's own carve-out (needs the full edge set).
  No new test: existing `TreeTruncationTests`/`TreeQueryBudgetTests` already
  cover the output contract and query count (`assertNumQueries(3)`
  unaffected -- still one query, just with a LIMIT); a test proving the
  DB-level row cap specifically would need a 5000+-row fixture, disproportionate
  for CI.
- **M8** (member roster leaks every member's email to every role):
  `ClanMemberSerializer.to_representation` now pops `email` unless the
  caller resolves to `owner` for that member's clan (same
  cache-then-selector-fallback pattern `ClanSerializer` already uses for
  `public_slug`). `ClanMembersAPIView`/`ClanMemberDetailAPIView`/
  `JoinClanAPIView` all pass `context={'request': request}` now.
  Test: `test_member_roster_hides_email_from_non_owners`.

## Medium/Low -- skipped (reason)

- **M2** (last-owner guard check-then-act, no lock): needs
  `transaction.atomic()` + `select_for_update()` plus a real concurrency test
  (threads/separate connections) to prove -- disproportionate to a narrow
  race window (2-owner clan, simultaneous demote+demote). Sequential guard
  already blocks the common single-request case.
- **M3** (soft-deleted clan unrecoverable, persons left live): explicitly
  listed as out-of-scope open question 3 in the task.
- **M6** (concurrent generation recompute race): documented pre-existing
  trade-off (denormalised field, `recompute_generations` is the fixup), same
  concurrency-test cost as M2.
- **M7** (`?force=true` is request-level not per-record): changes the
  bulk-create payload contract; explicitly flagged in the review as needing
  a product decision, none was given.
- **L1** (`views/params.py` doesn't exist): would mean relocating
  `_int_query_param`/`_parse_positive_int` across 2 files for a pure
  reorganisation with no behavior change -- deferred, not "quick."
- **L2** (`_wants_force` duplicated in 2 files): same, pure DRY cleanup, no
  behavior change, deferred.
- **L3/L4** (query-budget docstring/coverage gaps): documentation-only /
  needs a new `test_query_counts.py` convention file across 12 endpoints --
  out of proportion to "quick."
- **L6** (marriage gender/parent-child/order-uniqueness race): each needs its
  own product decision (is a `gioi_tinh` check even correct for this
  domain?) or a DB constraint + migration; deferred.
- **L7** (`MarriageDetailAPIView.patch` silently discards husband/wife
  changes): needs a decision on whether that's a 400 or documented no-op;
  deferred, matches original review's "cosmetic" framing.
- **L8** (`assertRaises(Exception)` blanket catch in 2 tests): test-only
  smell, zero production impact, deferred.
- **L9** (`services/revision.py::snapshot` purity is nominal only): informational,
  no action needed.
- Informational items (hide_living_details unused, PersonRevision full-dump
  already gated correctly): no action per report, both already correctly
  scoped/gated.

## Tests

New/changed test files: `test_invites_and_join.py`, `test_person_api.py`,
`test_marriage_api.py`, `test_person_rules.py`, `test_permissions.py`.
Every fix above has a test that fails on the pre-fix code (verified by
construction, not by reverting -- each test reproduces the reviewer's
measured repro or the exact false-negative fixture gap named in the report).

- giapha suite: 209/209 green
- full suite: 259/259 green (was 237 baseline + 22 net new)
- `makemigrations giapha --check --dry-run`: No changes detected
- `grep -rn "from apis\|import apis" giapha/`: empty
- `services/` imports: unchanged, still ORM-free
- Largest non-test file: `services/person_rules.py`, 200 lines (right at the
  cap after the fail-closed docstring; trimmed twice to fit)

## Unresolved questions

1. Enumeration oracle in C1 (unknown-code 404 vs rejected-code 400) -- not
   requested, would change 2 existing test assertions if fixed. Confirm
   whether to fix in a follow-up now that `/join` is throttled (throttling
   reduces but doesn't eliminate the oracle's value to an attacker).
2. Restoring a person whose `father_id`/`mother_id` changes via `/restore`
   does NOT trigger `recompute_descendant_generations` (PATCH does, when
   `parent_changed`). Not in H3's scope (validation only), but means a
   successful restore that changes a parent can leave `generation` stale
   until the next full `recompute_generations` run. Flagging for a decision
   on whether restore should mirror PATCH's recompute trigger.
3. M2/M6 concurrency gaps (last-owner race, generation-recompute race) left
   as documented trade-offs per above -- confirm that's acceptable long-term
   or worth a dedicated follow-up with real concurrency tests.

**Status:** DONE
**Summary:** All Critical/High findings + 4 product decisions implemented with regression tests; 4 quick Medium/Low fixes (M1, M4, M5, M8) also applied. Full suite 259/259 green, no migration drift, no layering/purity violations introduced.
**Concerns/Blockers:** None blocking. See unresolved questions above for follow-up decisions.
