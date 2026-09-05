# Giapha Phases 1-4: Green Tests Masked Five Real Defects

**Date**: 2026-09-05 13:30  
**Severity**: High  
**Component**: `giapha/` Django app (clan, person, marriage, invite models)  
**Status**: Resolved  

## What Happened

Completed phases 1-4 of the Vietnamese family-tree module (6 models, admin interface, CRUD endpoints, 10 validation rules, revision tracking, tree traversal). Test suite reported 237 green tests. Code review deployed an adversarial 31-test probe suite against a real MySQL database, which immediately found five production-grade defects that the passing test suite had completely concealed. All defects were fixed and re-verified. Final state: 261 tests green (50 pre-existing `apis/`, 211 new `giapha/`).

## The Brutal Truth

This is the clearest recent example of a testing strategy that optimized for passing rather than for safety. The test suite was correct in measuring that `giapha/` did what we told it to do — it just wasn't measuring the right things. We shipped authentication and authorization logic that looked sound under unit test but crumbled under adversarial probing with a real database. If we'd cut the code review short or trusted the green suite to imply correctness, we'd have deployed role escalation, data corruption, and unrevocable bearer tokens that granted ownership. The frustrating part is that none of these defects were edge cases or obscure failure modes — they were direct consequences of unexamined design assumptions that a thirty-minute probe found immediately.

## Technical Details

### Defect 1: Invite Codes Granted Permanent, Unlimited, Unrevocable Ownership

- `Clan.Invite.max_uses` defaulted to 0 (database default), interpreted as unlimited
- `expires_at` defaulted to None, interpreted as never expires
- `owner` was in the role choices without restriction
- Only `POST /join` was exposed; no list, no revoke endpoints
- **Result**: Two unrelated users each redeemed the same invite code. Each became owner of the clan. A leaked code had zero remediation path.
- **Fix**: Model-level constraint to `max_uses >= 1`, serializer to whitelist roles to `['member', 'manager']` only, `/join` redemption to check role choices explicitly and fail closed, exposed DELETE `/invites/{id}/` for revoke.

### Defect 2: `generation` Field Never Computed on Create

- Phase 4's headline feature: `generation` derived field tracks depth in tree
- Recompute hook ran only on PATCH, not on POST
- **Result**: Every person created through normal API path got `generation: null`
- Field was also in serializer write fields, so client could POST `"generation": 999`
- **Fix**: Computed on POST via `save()` override, removed from write fields, made read-only

### Defect 3: Bulk-Create N+1 Query Explosion

- Creating 20 parented rows (with `father_id`) issued 66 queries instead of guaranteed 3-query contract
- Guard test passed only because fixture rows had no `father_id`, measuring the single case where bug couldn't fire
- **Result**: False-negative test, worse than no test — manufactured confidence
- **Fix**: Explicit `select_related('father', 'mother')` in bulk write path, test fixture rewritten to include parented rows

### Defect 4: Restore Bypass Violated Core Cycle Validation

- Restore handler bypassed `validate_no_cycle` entirely
- **Result**: Reproduced end-to-end A↔B parent cycle through ordinary API calls into genuine MySQL
- **Fix**: Explicit cycle validation on restore, test case added with real cycle structure

### Defect 5: Safety Bound Failed Open in Tree Traversal

- `descendants()` iterator had iteration cap (to prevent infinite recursion on malformed trees)
- When cap fired, returned *partial* results instead of raising
- **Result**: `validate_no_cycle` would receive partial set, wave a real cycle through
- **Fix**: Raised exception on cap, added explicit cycle detection to guard before graph walk

## What We Tried

1. **Unit tests in isolation**: Passed. Measured happy path and documented rules correctly, but didn't probe the actual constraints the rules needed to enforce.
2. **SimpleTestCase strategy**: Caught authorization boundaries well (cross-clan parent, cross-clan spouse all rejected correctly). Caught 404-not-403 discipline. But couldn't catch correctness issues in the core data model because the tests didn't exercise the model's invariants under adversarial input.
3. **Coverage metrics**: 87% on `giapha/`. Didn't correlate with defect density; the bugs were in heavily-covered code.

## Root Cause Analysis

Three patterns:

1. **Test design traded depth for breadth.** We wrote many tests for different code paths (invite, person CRUD, person, marriage, tree, restore, cli) but shallow tests for each. Each test fixture was minimal and didn't expose defects that required a realistic data structure (e.g., parented rows, real cycles, state transitions).

2. **An architectural invariant eroded silently.** `services/revision.py` imported the ORM, breaking the rule that `services/` stays database-free — the entire property on which `SimpleTestCase` strategy rests. The import was localized and easily fixed, but it went unnoticed because we didn't verify the invariant after each implementation. Erosion of this type compounds silently.

3. **Delegated work was trusted instead of verified.** A fix agent capped invite roles at the serializer, but didn't close the model field or `/join` redemption. The fix looked complete at the API boundary and was trusted. The rule: *the API is not the only writer.* Django admin, fixtures, batch imports, and direct ORM all bypass the API boundary. Validation at the boundary alone is never sufficient.

## Lessons Learned

1. **Adversarial testing mode matters more than test count.** Thirty-one targeted tests with a real database found more than 200+ isolation tests. The probe suite asked "what assumption would break this most easily?" rather than "does the happy path work?"

2. **False-negative tests are expensive; prefer verification to trust.** The N+1 test passed only in the case where the bug couldn't fire. It's safer to assume delegated work is incomplete and verify it than to trust a passing test. Three minutes of verification (running the actual queries, examining the call graph) would have caught this before merge.

3. **Safety bounds must fail closed.** The iteration cap that returned a partial set and hoped the caller noticed was a time bomb. Bounds that fail open (return wrong answer, silently) are worse than no bound. Always raise when a safety limit is hit.

4. **Invariants must be verified, not just documented.** The "services are ORM-free" rule existed in documentation but had no enforcement. A simple check (import ast, scan for ORM references in services/) would have caught the violation immediately.

5. **Validation must happen at every write boundary, not just the API.** Django admin can write rows directly. Django fixtures can write rows directly. Batch imports can write rows directly. If a constraint is important, it belongs in the model and in every entrypoint. Serializer validation alone is not sufficient.

## Next Steps

1. **Phase 5 is genuinely blocked** on the Hồ Ngọc Đức lunar calendar mapping (`k` parameter → lunar month). A guessed implementation would put every giỗ (death anniversary) date off by a day, which is the module's entire reason to exist. Research required.

2. **Performance claim left unticked in plan.** Spec says "p95 < 500ms at 1,000 persons," but largest fixture is 24 persons. Query count is proven at 3. Wall-clock latency is untested. Don't tick this until benchmarked.

3. **MySQL 5.7 has no `WITH RECURSIVE`.** Entire clan loads in one query, walked in Python. Closure table and materialized path were considered and rejected as over-engineering below the 5,000-person ceiling. Revisit if clan sizes grow.

---

**Status:** DONE  
**Summary:** Phases 1-4 shipped with 237 green tests. Adversarial code review found and fixed five production defects (invite roles, null generation, N+1 bulk create, restore cycle bypass, partial tree traversal). Final state 261 tests green; all defects resolved and re-verified.  
**Concerns/Blockers:** Phase 5 (lunar calendar) blocked on Hồ Ngọc Đức `k`-to-month mapping. Performance claim at 1,000 persons untested (only 24-person fixture). MySQL 5.7 limitation constrains tree walk strategy but acceptable at current scale.
