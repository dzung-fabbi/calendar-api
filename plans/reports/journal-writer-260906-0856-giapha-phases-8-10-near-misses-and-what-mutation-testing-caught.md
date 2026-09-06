# Giapha Phases 8-10: Two PII Leaks That Shipped Green, and Why Mutation Testing Mattered

**Date**: 2026-09-06 08:56
**Severity**: High (phases 8-9); Medium (phase 10)
**Component**: `giapha/` Django app — presigned S3 uploads (phase 8), public sharing (phase 9), test hardening (phase 10)
**Status**: Resolved; integration unverified (S3, FCM)

## What Happened

Shipped phases 8, 9, 10. Combined suite **720 tests passed, 6 skipped**. Two commits on `master`, not pushed:

- `d725fc2` phases 8-9 — presigned S3 photo upload (`services/storage.py`, 4 endpoints), public gia phả sharing (whitelist serializers, per-liveness SQL field lists, 404-only surface, throttle scope, `noindex`)
- `bc29629` phase 10 — test hardening (shared `testkit/` package, query budgets, shape snapshots, security matrix, docs across both `apis/` and `giapha/`)

Phase 8 introduced `StorageService`, `PhotoObject`, `PresignedUpload`, mocked S3 integration with no real-bucket E2E (credentials unavailable, project-owner decision — same posture as phase 6's unverified FCM). Phase 9 added public-read endpoints (`GET /public/{slug}`, `GET /public/{slug}/tree`), `PublicClanSerializer`, `PublicPersonSerializer`, `PublicTreeEdgeSerializer`, `public_slug` field, visibility control, rate limiting. Phase 10 enforced query budgets against fixtures (1,000-person clan), shape snapshot assertions, mutation-verified security properties.

Review scores: phase 8 **6.5/10** (storage mocking adequate, real upload path deferred); phase 9 **7.5/10** (caught two PII leaks after code review, not test review).

## The Brutal Truth

Phase 9's implementation reached "complete, all tests green" with two active security failures that would have published PII to anyone with a link.

**First:** adoption and step-child status of living people. `PublicTreeEdgeSerializer` returned its dict verbatim (no whitelist), exposing `parent_kind` (`ruot`/`nuoi`/`ke`) — the only public record of whether a living person was adopted or has step-siblings. The field was never added to the phase's own security matrix; the test fixture had zero parent links, so the test asserted nothing.

**Second:** `_is_living()` fail-open. A single stray death field (e.g., `date_death` only, or `place_death` only) flipped a living person into the dead person's serializer branch and published their full biography. Reachable via Django admin (`ModelAdmin`, no `clean()`), CSV import, or raw `update()`. A person marked accidentally dead — even with just one column set — became public.

Worse: the first remained unfound until prose code review read `PublicTreeEdgeSerializer.to_representation()`. The second would have shipped untouched if a reviewer hadn't asked "what if `_is_living()` got only some of the death columns?"

Phase 8's root bug (field exclusion insufficient) and phase 9's rate-limit defect (NUM_PROXIES unset, throttle keyed on caller's own header) were found by reviewers mutating code and running probes, not by reading green test output. Tests had not even tried the things that broke.

## Technical Details

### Phase 8 review — 6.5/10, shippable with concerns

- **High**: removing `photo_key` from `_WRITE_FIELDS` did not close the write path. `POST .../restore/{revision_id}` re-applies fields from stored revision payloads with no prefix check, no HEAD existence validation, no storage-config requirement. A foreign-key `photo_key` restored, `head_object` never called, presigned URL minted. Proven by probe: restore *any unrelated edit*, and the profile points at a deleted object forever while the live one orphans.
- **High**: unconditional data corruption with no attacker needed. Replace a photo (correct flow), then restore an unrelated text edit from months ago — the revision payload still carries the old `photo_key`, gets re-applied, live photo orphaned, profile now dangling.
- **Medium**: mocked S3 means signature validation, CORS rules, region matching all unverified.

### Phase 9 review — 7.5/10, shippable after critical fixes

- **Critical (found via prose review)**: `PublicTreeEdgeSerializer.to_representation` returned dict verbatim. `edges` was an unguarded passthrough, exposing `parent_kind` (`ruot`/`nuoi`/`ke`) for living people to anyone with a link. The field was absent from the phase's security matrix. The fixture had zero parent links, so the edge test passed vacuously and asserted nothing.
- **Critical (found via mutation + probe)**: `_is_living()` required all three death columns NULL. Any single stray column (reachable via admin, CSV, raw `update()`) flipped a living person onto the dead branch. A person marked dead only by `date_death`, orphaning `date_birth`, published full biography.
- **High (found via mutation + probe)**: `visibility` PATCH endpoint never touches `public_slug`. Revoke visibility (clears slug in-place), re-enable, and the *old slug returns* — the docstring claimed "always mints DIFFERENT slug." It didn't. A previously-leaked link stayed active.
- **High (found via probe)**: rate limit ineffective. `NUM_PROXIES` was unset, so DRF keyed throttle on raw `X-Forwarded-For` string. Caller controls their own bucket. Measured: 61 of 61 requests returned 200 with rotating header. 40-bit invite codes had no brute-force protection.

### Phase 10 verification — query budgets, shape snapshots, mutation matrix

- `/xung-ho`: 3 queries baseline (4 for in-law spouse case) against spec target ≤2. Defence-in-depth cost: one requery per liveness branch keeps a living person's death columns out of memory.
- `/public/{slug}/tree`: 4 queries against spec target ≤3. Same single-requery cost as above, trade-off documented.
- `TestCaseMultiApp` suite (`testkit/`) combined `apis/` and `giapha/` tests. Found pre-existing: `apis/tests/snapshots/values_appointment_date.json` hardcoded `user_id: 2` (MySQL AUTO_INCREMENT). Any giapha test creating User first shifted it (measured 54, then 334). Invisible for as long as suites ran separately.
- One bug found but deliberately NOT fixed: `apis/views/good_day.py` queries `HiepKy` with no `.order_by()`, then sorts only on `percent`. Tied rows come back in MySQL's chosen order, non-deterministic. Low severity (rare tie), known, deferred.
- Mutation test for phase 9's edge builder: deleted junk into it, serializer projection blocked it anyway. Proved the guard was independent, not a mirror.

## What We Tried

- **Reading phase 8 code for logic errors**: found little. The reviewer ran a restore probe and watched `photo_key` re-apply; that is how it surfaced.
- **Reading phase 9 code for security promises**: found two issues (visibility slug regeneration, rate limit bucket selection). The two PII leaks required either mutating code (replacing `to_representation` passthrough with projection, altering `_is_living()` to AND vs OR) or running adversarial probes (restore a foreign-key revision, flip a single death column).
- **Green test suite on whitelist**: the suite had key-set canary tests proving "any new key fails" for *nodes* only. It said nothing about `edges`.
- **Trusting docstrings again**: "visibility re-enable mints a different slug" and "rate limit throttles on IP" were the written contract. The code broke both. Comments claiming security properties need the same adversarial verification as the code itself.

## Root Cause Analysis

1. **Field exclusion from a write serializer is insufficient defense if old records already carry the field.** Removing `photo_key` from `_WRITE_FIELDS` protects only *new* revisions. Every revision already in the database — including those created before phase 8 landed — keeps the field. The exclusion had to be enforced on *read*, in `restore()`, by filtering the keys that get re-applied. A general principle: when adding a field to an exclusion list, ask whether the database already contains it in old rows.

2. **A whitelist that covers half the payload is a blacklist in disguise.** `PublicTreeEdgeSerializer` had whitelist canary tests; they checked nodes only. The edge dict was a passthrough. Riding out through that hole: adoption and step-child status, published for living people to anyone with a link. When the fixture had zero parent links, the edge test passed vacuously. A test over an empty collection asserts nothing; it only becomes a real test when the data shape changes.

3. **Comments claiming security guarantees need mutation testing.** All three phase-9 failures had confident comments describing behaviours the code did not provide:
   - `_is_living()`: "Returns True if person is deceased (all death columns null)" — actually true as written, but the name `_is_living()` inverts the implication. The real failure was structural: no `clean()` method on the model to enforce that all-or-none death columns. Any caller setting one column without the others broke the invariant.
   - `visibility` + `public_slug`: "Re-enabling visibility always generates a new public slug." It doesn't; `PATCH` never regenerates.
   - Rate limit: `NUM_PROXIES` unset means "use the raw request header as the key" — the docstring said "throttle by IP." It did neither.

4. **Mutation testing distinguished real tests from decorative ones.** Phase 8: deleting the mandatory HEAD-existence check left all 26 upload tests green. Phase 9: reverting the edge projection bug failed exactly the intended tests; proving the guard was real. Reverting the `_is_living()` fix and the visibility fix failed their respective suites. The only technique that reliably proved "this test measures the bug" was: revert the fix, watch tests fail with a meaningful count (not vacuous pass).

5. **Two pre-existing bugs surfaced only when suites combined.** `apis/` and `giapha/` tests ran separately for months. Running them together in one invocation revealed:
   - `values_appointment_date.json` hardcoded `user_id: 2`. On `apis/` alone, users were 2+ (no giapha user creation). On `giapha/` alone, users were 1+ (giapha's User models start at 1, run first, shift everything). Combined: the test fragility was invisible.
   - Fix: pinned fixture primary keys rather than normalising the snapshot. The pinned values matched exactly — no re-recording needed.

## Lessons Learned

1. **Removing a write-side field is not the same as forbidding it.** If old payloads in the database carry it, and a restore-from-snapshot flow iterates the stored keys, the old field re-applies. The exclusion must move to read-time — on restore, filter keys before re-applying them. More general: data migrations that forbid a field going forward must also purge it from old records, or enforce the exclusion at the read boundary.

2. **Empty-collection tests pass vacuously.** A fixture with zero parent links means `edges` is empty, and `for edge in edges` never runs. The test "passes" without testing anything. Real verification only arrives when the data shape gains the case being tested. For security whitelist tests: either pre-populate with examples of the denied field, or document that the test is aspirational until data appears.

3. **Security comments need mutation verification.** If a comment says "this always does X," mutate the code to not-X and run the test suite. A green result means the comment is a lie or the guard is somewhere else. Efficient: revert-test, revert the revert. Takes 30 seconds. Finds lies in seconds.

4. **Structural invariants beat procedural ones.** `_is_living()` checking all three death columns is procedural — someone must remember to call it correctly. A model with `clean()` that raises if any-but-not-all death columns are set *structures* the invariant into the model. A rate limit that keys on a stable identifier (user id, internal IP) is structural; one that says "set NUM_PROXIES correctly" is procedural. Procedures fail when someone doesn't follow them. Structures fail visibly.

5. **Honest numbers beat green ticks.** `/xung-ho` is 3 queries (4 worst case, in-law spouse) against a target of ≤2. `/public/{slug}/tree` is 4 against ≤3. The second deficiency is the direct cost of phase 9's defence-in-depth: one requery per liveness branch keeps living-person death columns out of memory during serialization, blocking the PII leak. Recording the real number with the trade-off documented is more useful than either (a) lying about it to get a checkbox, or (b) leaving it unmeasured.

## Next Steps

1. **Phase 8's real S3 integration is unverified.** No real bucket, no credentials. Every test mocks the storage layer. Expect the first real `PUT` to fail on signature version, CORS rules, or region mismatch — the least observable points in the flow. Must test against a real bucket before calling this production-ready.

2. **Phase 6-9 integration unverified: FCM + photo upload.** A received push with a photo attachment has never been tested end-to-end. Mocks are complete and green; reality is unknown.

3. **Query budgets documented but not met:** `/xung-ho` at 4 (spec ≤2), `/public/{slug}/tree` at 4 (spec ≤3). Trade-offs recorded; renegotiation deferred.

4. **Pre-existing `remind_appointment_date.py` bug:** still uses `timezone.localtime()` under `TIME_ZONE='UTC'`, same one-day-off as phase 6 deliberately avoided. Not phase 8-10 scope; owner decides.

5. **Open Low:** `update_or_create` in reminder command can downgrade a `sent` log row under overlapping runs (no lock). Unobserved in practice; deferred.

## Unresolved Questions

1. When does phase 8's real-bucket S3 integration happen, and who provisions it? Is the mock-only state a blocker for release?
2. Will phase 6's FCM push ever reach a real handset, or does this ship with mocks-only success criteria?
3. Do `/xung-ho` and `/public/{slug}/tree` query budgets get accepted at 4 and 4, or does the spec get renegotiated to match them?
4. Should `_is_living()` gain a model-level `clean()` method now, or is the read-side check sufficient?
5. Does the rate limit need a real load test against a public endpoint to verify the fix holds under actual rotating-header attack patterns?

---

**Status:** DONE_WITH_CONCERNS
**Summary:** Phases 8-10 shipped, 720 tests green. Phase 9 reached "complete, tests pass" with two PII leaks (adoption status for living people published via `edges` passthrough; any single stray death column flipped person to public via `_is_living()` fail-open). Both caught by code review and mutation testing, not test output. Phase 8's restore-with-no-validation bug caught by probe. Phase 10 hardened suite (query budgets measured, shape snapshots, mutation matrix) and revealed pre-existing `values_appointment_date.json` fixture collision when suites combined.
**Concerns/Blockers:** S3 upload never tested against real bucket — mocked end-to-end. FCM push never reached real handset. Query budgets at 4 vs spec ≤2 and ≤3, trade-offs documented but unmet. `_is_living()` success requires remembering to call it; no structural enforcement. Three commits unpushed.
