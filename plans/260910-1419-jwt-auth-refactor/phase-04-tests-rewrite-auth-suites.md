# Phase 04 — Tests: rewrite the two DOT-bound suites, green the whole thing

**Priority:** P1 · **Status:** completed · **Effort:** 1h30m · **Blocked by:** phase 03

## Context links

- [plan.md](plan.md) · previous: [phase-03](phase-03-remove-django-oauth-toolkit.md)
  · next: [phase-05](phase-05-docs-sweep.md)
- Being replaced: `giapha/tests/test_auth_token_endpoints.py` (285 lines, imports
  `oauth2_provider.models.Application`) — **deleted**, not ported
- Being adapted: `apis/tests/test_auth_change_password_api.py` (210 lines, L19 imports
  `Application, get_access_token_model, get_refresh_token_model`)
- Rules: `docs/code-standards.md` → Tests, Queries ("Adding an endpoint means adding it to
  `test_query_counts.py`. The ceiling is the contract.")

## Overview

Two files import DOT and must change; one new file covers the three new endpoints; the query
ledger gains three entries. Everything else in the 579-test suite should pass untouched —
if it does not, the authentication class is wrong, not the test.

## Key insights

- **Only two test files import `oauth2_provider`** (verified by grep). Everything else
  authenticates with `force_authenticate`, which bypasses authentication entirely — so the
  bulk of the suite is genuinely indifferent to this refactor, and existing per-endpoint
  query budgets are unaffected.
- The new suite lives in **`apis/tests/`** because the endpoints do. It must assert against
  an `apis/` endpoint (`/api/me`), **not** `/api/gia-pha/clans`: the deleted file's
  cross-app reach is exactly the coupling `docs/code-standards.md` forbids. Anonymous-401 on
  the giapha side is already pinned by
  `giapha/tests/test_permissions.py::test_anonymous_gets_401_not_404` — re-run it, do not
  duplicate it.
- `cache.clear()` in `setUp` is mandatory for any test touching a throttled endpoint —
  `auth-login` is 20/hour per IP and the whole suite shares one process cache. Every existing
  `apis/tests/test_auth_*.py` already does this; copy the pattern, including the comment.
- `settings_test.py` swaps in `MD5PasswordHasher`. That changes `user.password`, hence the
  `pwd` fingerprint — fine, because the fingerprint is computed from whatever is in the
  column, but **never hard-code an expected fingerprint** in a test.
- To test an expired access token, inject `now=` into `encode_access_token` (phase 01 step 6
  made it injectable) rather than sleeping or freezing time.
- The 401-vs-403 downgrade trap (phase 02) is invisible to a lax assertion —
  `assertEqual(401, ...)`, never `assertIn(response.status_code, (401, 403))`.

## Requirements

**Functional** — new `apis/tests/test_auth_login_api.py` covers:

| # | Case | Expect |
|---|---|---|
| 1 | login, form-encoded body | 200, exactly the four keys, `token_type == 'Bearer'` |
| 2 | login, JSON body | 200 |
| 3 | login, missing `password` | 400 with a `password` field error |
| 4 | login, wrong password | **401**, `{"detail": ...}`, no `access_token` |
| 5 | login, unknown username | 401, byte-identical body to case 4 |
| 6 | login, `is_active=False` user, right password | 401, same body |
| 7 | issued access token on `GET /api/me` | 200 |
| 8 | no `Authorization` header on `GET /api/me` | **401** (not 403) |
| 9 | tampered signature / garbage bearer value | 401 |
| 10 | expired access token (minted with `now=` in the past) | 401 |
| 11 | refresh rotates | 200, new pair ≠ old; old refresh replayed → 401; new access works |
| 12 | refresh with unknown / garbage token | 401 |
| 13 | logout | 204, empty body; then refresh with that token → 401 |
| 14 | logout with an unknown token | 204 (no oracle) |
| 15 | password change kills a live access token | `/api/me` 200 before, **401** after, and `RefreshToken.objects.filter(user=…).count() == 0` |
| 16 | public endpoint with no header (`/api/home` or `/api/get-config`) | 200 — the "return `None`" guard |

**Non-functional**
- File < 200 lines: use one `_login()` helper and one `_bearer(token)` helper.
- Unit tests for `apis/services/jwt_tokens.py` go in `apis/tests/test_services.py`
  (`SimpleTestCase`, no DB): round-trip encode/decode, fingerprint changes when the password
  hash changes, `decode` raises on a token signed with a different key, `hash_refresh_token`
  is 64 hex chars, two `generate_refresh_token()` calls differ.

## Related code files

**Create**
- `apis/tests/test_auth_login_api.py`

**Modify**
- `apis/tests/test_auth_change_password_api.py` — drop the DOT import and the two
  `Application.objects.create(...)` fixtures (L38-45, L160-167); `TOKEN_URL` becomes
  `/api/auth/login`; the login body loses `grant_type`/`client_id`/`client_secret` and keeps
  `username`/`password`; token-count assertions move to `RefreshToken.objects.filter(user=…)`.
  The second class (`PublicClientAuthTokenTests`, L153+, which pins the
  send-the-secret-or-not table) is **deleted outright** — it tests a concept that no longer
  exists. The docstring's claim that `/auth/token` is "deliberately untouched" must go.
- `apis/tests/test_services.py` — add the `jwt_tokens` unit tests
- `apis/tests/test_query_counts.py` + `apis/tests/snapshots/query_budgets.json` — three new
  budgets: `auth_login`, `auth_refresh`, `auth_logout`

**Delete**
- `giapha/tests/test_auth_token_endpoints.py`

## Implementation steps

1. `git rm giapha/tests/test_auth_token_endpoints.py`.
2. Write `apis/tests/test_auth_login_api.py` against the table above. Module docstring says
   what the file guards: *the three endpoints are the only login path; 401 (never 403) is the
   answer to every bad credential; rotation is single-use.*
3. Rewrite `apis/tests/test_auth_change_password_api.py`:
   - imports: `from apis.models import RefreshToken`, no DOT;
   - `login()` posts `{'username': …, 'password': …}` to `/api/auth/login`;
   - the "old token dies" assertion stays exactly as it was — it is the behavioural contract
     that survives the mechanism change;
   - delete `PublicClientAuthTokenTests`;
   - keep `cache.clear()` in `setUp`.
4. Add `JwtTokenServiceTests` to `apis/tests/test_services.py` (`SimpleTestCase` — the module
   already runs there).
5. **Measure, never guess, the three new budgets.** Add the tests first with a deliberately
   wrong ceiling, read the `assertNumQueries` failure, then write the real number into
   `apis/tests/snapshots/query_budgets.json`. Expected shape:
   `auth_login` = user lookup + refresh INSERT; `auth_refresh` = row lookup + DELETE +
   INSERT; `auth_logout` = one DELETE. Mirror `test_auth_register`'s helper usage
   (`assert_post_within_budget`), and `cache.clear()` as that suite already does at L171.
6. `./scripts/run-tests.sh` — full suite, both apps in one invocation (the script's default).
   Target: the pre-existing 579 pass/4 skip count, minus the 17 deleted DOT tests, plus the
   new ones. Any *other* failure is a real regression — fix the code, not the test.
7. `./scripts/run-tests.sh apis.tests.test_api_snapshots` — proves no public endpoint started
   401ing (the "return `None`" guard).
8. `docker compose run --rm web python manage.py makemigrations --check --dry-run`
   → "No changes detected".

## Todo list

- [x] `giapha/tests/test_auth_token_endpoints.py` deleted
- [x] `apis/tests/test_auth_login_api.py` written, all 16 cases (expanded to 20)
- [x] `apis/tests/test_auth_change_password_api.py` de-DOT-ed, `PublicClientAuthTokenTests` gone
- [x] `jwt_tokens` unit tests in `apis/tests/test_services.py`
- [x] Three measured budgets in `test_query_counts.py` + `query_budgets.json`
- [x] `./scripts/run-tests.sh` fully green (856 tests, 0 failed, 7 skipped)
- [x] Snapshot suite green (public endpoints unaffected)
- [x] `makemigrations --check --dry-run` clean

## Deviations from plan

1. **Test cases expanded from 16 to 20**: Additional cases cover expired refresh row, non-Bearer scheme, and refresh after plain `set_password()`. Ensures password_fingerprint field validates correctly.
2. **Test name changed**: `test_unusable_password_account_is_pointed_at_the_reset_flow` renamed to `test_unusable_password_logs_the_caller_out` (now asserts 401 instead of a forward, since `set_unusable_password` rewrites the hash).
3. **`run-tests.sh` improved**: Now derives Docker network name from the running `db` container instead of hard-coding `calendar-api_default`, improving portability.
4. **Missing import fixed in `auth_password_change.py`**: Added `from rest_framework.throttling import ScopedRateThrottle` (required by phase 02's throttle_classes addition).

## Success criteria

- [x] `grep -rn "oauth2_provider\|client_secret\|/auth/token\|revoke-token" --include=*.py .`
  returns nothing outside `apis/migrations/0075_*`.
- [x] Full suite green on a **freshly created** test database (856 tests, 0 failed, 7 skipped).
- [x] Case 8 asserts `401` exactly — the guard against the DRF 403 downgrade.
- [x] Case 15 passes: password change kills live access tokens via `pwd` claim, refresh rows deleted.

## Risk assessment

| Risk | L×I | Mitigation |
|---|---|---|
| Budgets written from expectation, not measurement → a vacuous ceiling | Med×Med | Step 5's deliberate-fail-first procedure |
| Throttle bleed between tests (20/hour login) → flaky 429s | **High**×Med | `cache.clear()` in every `setUp`; a dedicated test asserts the 429 and clears afterwards |
| A test asserts `(401, 403)` and hides the downgrade bug | Med×High | `assertEqual(401, …)` only, in the new file |
| Deleting `giapha/tests/test_auth_token_endpoints.py` loses giapha auth coverage | Low×Med | `test_permissions.py::test_anonymous_gets_401_not_404` already covers it; confirm it runs green |
| MD5 hasher in tests hides a real fingerprint bug | Low×Low | Fingerprint is computed from the column, never hard-coded |
| Test-only user left `is_active=False` leaks into another test's fixture | Low×Low | Build inactive users inside the test, not `setUpTestData` |

## Security considerations

- Case 5 and case 6 must produce **byte-identical** bodies to case 4; assert the bodies are
  equal, not merely that each is 401 — that is the enumeration guard, and it is easy to lose
  to a well-meaning "more helpful" error message later.
- Case 14 (logout of an unknown token → 204) prevents logout becoming a token-validity oracle.
- No test may print or log a real token in an assertion message.

## Next steps

Phase 05 rewrites the documentation the old flow left everywhere.
