# Giapha Phases 5-7: Every Defect Was a Missing Negative Case

**Date**: 2026-09-05 21:43
**Severity**: High
**Component**: `giapha/` Django app — lunar calendar (phase 5), FCM giỗ reminders (phase 6), kinship term calculator (phase 7)
**Status**: Resolved, with one success criterion unverifiable in this environment

## What Happened

Shipped phases 5, 6, 7. Suite 357 → **579 passed / 4 skipped**. Three commits on `master`, **not pushed**:

- `61839cd` phase 5 — VN lunar calendar + death-anniversary endpoint (already complete and green at session start)
- `682e6ec` phase 6 — FCM HTTP v1 push, daily `remind_death_anniversary` command, per-user follow control
- `4b87729` phase 7 — Vietnamese kinship term calculator

Phase 6 introduced `ClanMember.person` (OneToOne binding a login to its node in the tree — did not exist before), `GioFollow` as **override-only** (no row = default "follows own direct ancestors", resolved at send time, nothing materialised), `DeviceToken`, `GioNotificationLog`; endpoints `toi-la`, `gio-follows`, `/devices`; migrations 0004/0005. Phase 7 added `GET /clans/{id}/xung-ho` with `a` defaulting to the caller's binding, across 9 pure service modules, no schema change.

## The Brutal Truth

Same lesson as phases 1-4, arriving by a different door: **every defect found this session was invisible to a fully green suite, and every one was a missing negative case.** Reviews that *read* code found little. Reviews that *ran* executable probes found Criticals. Three rounds, identical shape.

Worse, twice the code was contradicted by its own prose, and the prose was more confident than the code deserved. A test named `test_leaving_the_clan_drops_the_binding_not_the_person` passed while the exact leak it names was wide open.

## Technical Details

### Phase 6 review — 6/10, not shippable

- **Critical**: `GioFollow` rows outlived their `ClanMember`. A removed member kept receiving pushes naming a deceased person, from a clan for which every endpoint answered 404. This is precisely the leak the `ClanMember.person` design was chosen to prevent.
- **High**: failed reminders blocked for ~a year. `target = today + N` means each person is due on exactly ONE calendar day, so a `status='failed'` row was never retried. Two source comments asserted the opposite — arithmetically false.
- **High**: transient OAuth blip abandoned an entire run, because `{}` was overloaded to mean both "no credentials configured" and "token mint failed".
- **High**: `except IntegrityError` with no savepoint.

### Phase 7 review — 6/10, not shippable

- **Critical**: collateral descending ladder off by one, yielding `ông ↔ chắt` — not a reciprocal pair in Vietnamese. The same file's `TRUC` block had it right.
- **Critical**: a user's own wife resolved as `chị`, `confident: true`, because the spousehood check sat inside a loop over the partner's *other* marriages.
- **High**: the one real hole in the "never guess seniority" guarantee — maternal `cậu`/`dì` stored with `elder=None`, so a mother's elder brother resolved confidently with no `birth_order`. Table and docstring disagreed; the docstring was right.
- Plus 3 further High.

### Phase 7 verification — 8/10

- **High (new)**: the unfixed half of the wife bug. Spouse routing was still decided by autoincrement id, because the selector dropped `status`/`order`. A widow remarried to her late husband's younger brother was told to call her husband's elder brother `em`, `confident: true`.

## What We Tried

- **Reading the code**: found little. Both 6/10 verdicts came from probes, not from prose review.
- **Trusting docstrings**: actively harmful. Phase 6's dedupe comments, phase 7's caller lists and its `path`-is-nullable claim were all wrong, and one file contradicted itself. A wrong comment is worse than no comment — reviewers and the next implementer trust it.
- **63 green kinship tests**: let a self-contradicting terms file through.

## Root Cause Analysis

1. **Tests asserted the intended behaviour, never its absence.** Positive-only coverage cannot see a row that fails to be deleted, a retry that never fires, or a term returned for the wrong pair.
2. **Sentinel overloading.** `{}` carrying two meanings ("unconfigured" vs "failed") turned a retryable blip into run abandonment. Same class as phases 1-4's `max_uses=0` meaning unlimited.
3. **Identity leaked out of the domain into the storage layer.** Spouse ordering fell back to autoincrement id when the selector dropped `status`/`order` — a database implementation detail decided a kinship term.
4. **Two-sided data with one-sided validation.** Reciprocal ladders written independently per branch; `TRUC` correct, collateral off by one, in the same file, with nothing forcing agreement.

## Lessons Learned

1. **Require every fix to ship with a regression test observed failing when the fix is reverted.** One fixer wrote all tests first and recorded `FAILED (failures=24)` before implementing. That number is the only proof a test measures the bug.
2. **Reviewers should write throwaway probes against the real MySQL suite, then delete them.** Cheap, and the only technique that found anything this session.
3. **Property tests for two-sided data.** For the kinship vocabulary: if A calls B X, B must call A the documented counterpart. Hand-written, independent of the terms table, mutation-verified. Its absence is the single reason a self-contradicting file shipped past 63 tests. Honest caveat: **version one pinned ladder depth only**, so the `ông ↔ chắt` bug just fixed could have been reintroduced with the file still green. Strengthened only after a reviewer said so.
4. **Make hedging structural, not procedural.** `None` is a literal key in the lookup table, so a seniority-dependent term is *unreachable* without real `birth_order`. Getting vai vế wrong is a genuine insult in Vietnamese; `confident: false` beats a plausible answer. Same principle then applied to spouse routing — equal-rank marriages hedge rather than let a row id decide. A convention someone must remember is not a guarantee.
5. **Trust the code over the comment, and delete comments you cannot verify.**

## Next Steps

1. **Phase 6's real-device push is UNVERIFIED.** No Firebase project exists; every test mocks the FCM layer. It has never delivered a push. Exactly one success criterion is left unticked. Needs a real project plus one device before this is called working.
2. **Phase 7 query budget is 2/3/3, worst case 4.** Spec said ≤2. Recorded, not ticked.
3. **`apis/management/commands/remind_appointment_date.py`** still uses `timezone.localdate()` under `TIME_ZONE='UTC'` — the same one-day-off bug phase 6 deliberately avoided. Out of scope all session; owner decides.
4. **Open Lows**: `update_or_create` can downgrade a `sent` log row under overlapping runs (no lock); a member bound to a soft-deleted node keeps resolving an ancestor line; `parent_kind` ignored, so adopted children get blood terms.
5. **Phases 8 (blocked on S3 credentials), 9, 10 remain.** Three commits await push.

## Unresolved Questions

1. Who provisions the Firebase project, and does phase 6 ship before a real push is observed?
2. Is 4 queries worst case acceptable for `xung-ho`, or does the ≤2 budget get renegotiated in the spec?
3. Does the `remind_appointment_date.py` timezone bug get fixed now, or does `TIME_ZONE` change globally (wider blast radius)?
4. Do overlapping reminder runs actually occur in the target deployment — i.e. is the `sent`-downgrade Low real?
5. Should `parent_kind` (adopted vs blood) change kinship terms at all, or is the current blood-term default correct Vietnamese usage? Needs a native-speaker ruling, not an engineering one.

---

**Status:** DONE_WITH_CONCERNS
**Summary:** Phases 5-7 shipped, 579 tests green. Three review rounds found 3 Critical + 8 High, all invisible to a green suite and all missing negative cases (`GioFollow` orphans, failed reminders blocked ~1 year, `{}` sentinel overload, `ông ↔ chắt` non-reciprocal ladder, own wife as `chị`, spouse routing by autoincrement id). All fixed with revert-verified regression tests; reciprocity property test added and then strengthened.
**Concerns/Blockers:** FCM push never delivered to a real device — mocked end to end, one success criterion unticked. `xung-ho` query budget 4 worst case vs spec ≤2. Pre-existing `remind_appointment_date.py` timezone bug untouched. Three commits unpushed.
