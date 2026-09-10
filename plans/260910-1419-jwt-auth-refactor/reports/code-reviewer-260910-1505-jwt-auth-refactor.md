# Code review: JWT auth refactor (django-oauth-toolkit removed)

Scope: uncommitted working tree, 2026-09-10. New files read fully; modified files diffed.
Suite already green (853/7 skip) — not re-run. Verified DOT 2.2.0 FK graph against upstream
`oauth2_provider/models.py` at tag 2.2.0.

## CRITICAL

### C1. Migration 0075 will fail on every database that actually has the DOT tables
`apis/migrations/0075_drop_oauth2_provider_tables.py:26`

DOT 2.2.0 has a **circular** FK the plan's map (phase-03 L66-70) omits:
`AbstractAccessToken.source_refresh_token = OneToOneField(REFRESH_TOKEN_MODEL, SET_NULL)`
(upstream migration `0002_auto_20190406_1805`). So `oauth2_provider_accesstoken.source_refresh_token_id`
references `oauth2_provider_refreshtoken`, while `refreshtoken.access_token_id` references
`accesstoken`. MySQL 5.7 with `FOREIGN_KEY_CHECKS=1` rejects the first statement
(`DROP TABLE IF EXISTS oauth2_provider_refreshtoken`) with ERROR 1217/3730 "referenced by a foreign
key constraint". No drop order satisfies a cycle. The test DB passes only because the tables never
exist there (`IF EXISTS`), so the suite cannot catch this. Result on prod: 0074 applied, 0075 aborts,
deploy half-done.

Fix (robust, constraint-name independent): make `SET FOREIGN_KEY_CHECKS=0;` the first and
`SET FOREIGN_KEY_CHECKS=1;` the last element of the `RunSQL` list (session-scoped; RunSQL runs on one
connection). Alternative `ALTER TABLE ... DROP FOREIGN KEY <hash-name>` is fragile. Update the module
docstring and phase-03 FK map. Verify by running `migrate` against a DB restored from a prod dump (or
one where `migrate oauth2_provider` ran on the previous commit) BEFORE release.

## HIGH

### H1. Password changes outside the two API views leave refresh tokens alive
`apis/selectors/auth_tokens.py:22-37`, `apis/views/auth_login.py:91-94`

Only `/api/auth/change-password` and `/reset-password` call `set_password_and_revoke_tokens`. Django
admin's `UserAdmin` password form (`/admin/auth/user/<id>/password/`), `manage.py changepassword`,
and any shell `set_password()` rewrite `user.password` without touching `apis_refreshtoken`. Access
tokens die via `pwd` (correct), but the surviving refresh row re-mints a NEW access token carrying
the NEW fingerprint. "Admin resets a compromised account" — the scenario `auth_tokens.py` L3-4
names — therefore does not evict the attacker. Not a regression vs DOT, but the model/selector
docstrings claim the invariant is universal.

KISS fix: store `password_fingerprint(user.password)` on `RefreshToken` at issue; in
`consume_refresh_token` require `row.pwd == password_fingerprint(row.user.password)`. One column, no
signals, and it makes refresh die on ANY password write. (Alternative: `pre_save` on User.)

## MEDIUM

### M1. Raw refresh token not masked in Django error reports
`apis/views/auth_login.py:77`, `:97`

Login masks `password` via `sensitive_post_parameters` on `dispatch`; refresh/logout do not mask
`refresh_token`. A 500 inside `consume_refresh_token` (DB error) would put the live raw token in
the POST dict of the error report / Sentry event. Add
`@method_decorator(sensitive_post_parameters('refresh_token'), name='dispatch')` to both views and
`@sensitive_variables('raw')` on the three selector functions (locals are also dumped).

### M2. Throttle activation is a production behaviour change, not only a bugfix
`auth_register.py:26`, `auth_password_reset.py:107,141,161`, `auth_password_change.py:32`, `auth_login.py:64,82`

Before this diff `throttle_scope` was inert everywhere (no `DEFAULT_THROTTLE_CLASSES`) — register,
forgot, reset, change had NO limit in prod. Now six scopes go live, per-IP, keyed on
`NUM_PROXIES`. Deployment guide L90 says prod sets `DJANGO_NUM_PROXIES=1`; if that var is absent
or a CDN is added in front of nginx, every user shares one bucket → 20 logins/hour site-wide.
Needs a release-note line and a post-deploy check (login from two IPs, inspect 429). LocMem cache
means the effective limit is rate x gunicorn workers (already documented). Code is correct.

## LOW

### L1. `sub` minted as int — free to fix now, costly later
`apis/services/jwt_tokens.py:8-10, 62`
Docstring argues "every live token was minted this way, fixing would log everyone out" — but at
first deploy NO tokens exist (all DOT tokens die anyway). PyJWT >= 2.10 rejects non-str `sub` by
default, so the pin becomes a future footgun. Mint `str(user_id)` now; `User.objects.get(pk='5')`
works unchanged. Zero cost today, non-zero later.

### L2. consume + issue not atomic — acceptable, say so
`apis/views/auth_login.py:91-94`. A failure between DELETE and INSERT costs the user one re-login;
it can never yield two live tokens (fail-closed). Acceptable. If desired, `with transaction.atomic()`
around both calls is free and keeps the rowcount race check valid (InnoDB DELETE is a locking read;
the loser blocks then affects 0 rows).

### L3. Untested paths
- Expired refresh row → 401 (`refresh_tokens.py:59` filter has no test).
- Non-Bearer scheme (`Authorization: Basic x`) → `None` (200 on `/api/get-config`, 401 on `/api/me`).
- Refresh for a user whose password changed via plain `set_password()` (would pin H1).

## NIT
- `authentication.py:57` `compare_digest` on `str` raises `TypeError` (500) if a *signed* token
  carries a non-ASCII `pwd`. Unreachable without the key; `.encode()` both sides makes it total.
- `test_auth_change_password_api.py` `test_unusable_password_account_is_pointed_at_the_reset_flow`
  now asserts 401 — name is stale.
- `auth_register.py:4` docstring line now exceeds wrap width after edit.

## Verified OK (per checklist)
1. **JWTAuthentication**: returns `None` on missing/non-Bearer (L39-40); `authenticate_header`
   present (401 not 403, pinned by `test_anonymous_is_401_not_403`); `compare_digest` on `pwd`;
   `sub` None/str/list/dict → `DoesNotExist`/`ValueError`/`TypeError` all caught; float `sub`
   truncates via `int()` but needs the signing key. No A→B path: `sub` is signed and `pwd` is
   bound to that row. `jwt.InvalidTokenError` covers Decode/Expired/InvalidSignature/InvalidAlgorithm
   in PyJWT 2.6; `UnicodeDecodeError` caught.
2. **jwt_tokens**: `algorithms=['HS256']` pinned, constant not setting; `exp`/`iat` tz-aware UTC
   (PyJWT `utctimetuple`); SECRET_KEY fallback fine — settings L36-41 refuse the dev key when
   DEBUG off; 64-bit fingerprint is a change-detector inside a signed token, collision 2^-64,
   leaks nothing usable without the 22-char salt. No weakening.
3. **Refresh**: rowcount-checked DELETE by pk = correct race guard under autocommit or
   ATOMIC_REQUESTS; `expires_at__gt` filter; sha256 at rest (right call for 256-bit random);
   `unique=True` + FK index; `is_active` checked after consume (fail-closed).
4. **Views**: 401 via `Response`, single generic message; inactive folded by `ModelBackend`;
   `sensitive_post_parameters` on `dispatch`; `authentication_classes=()`; logout unthrottled OK
   (1 indexed DELETE, 256-bit token). DRF default `trim_whitespace=True` on `password` is
   consistent with Register/Change/Reset serializers — no lockout.
5. **0074** matches model exactly; **0075** depends on 0074, list of statements, `IF EXISTS`,
   reverse noop — but see C1.
6. **requirements**: no source imports of oauthlib/jwcrypto/Deprecated/wrapt/oauth2_provider;
   `cryptography`/`cffi`/`pycparser` retained for python-jose (correct).
7. **Leftovers**: only deliberate comments — `apis/urls.py:53`, `auth_login.py:4`,
   `settings.py:193`, `djangopj/urls.py:4-5`, `0074:7`. `request.auth` has no consumers.
8. **Standards**: all new files < 200 lines (max 176, test); docstrings explain WHY; flat payload
   on the three token endpoints; Vietnamese messages; query budgets 2/3/1 match the code paths.
9. **Tests**: pin 401, byte-identical bodies (L91-98), single-use refresh (L133-142), `pwd`
   revocation (L166-176). `cache.clear()` in `setUp`, fresh `User.objects.get` for the
   Django 3.1 shared-fixture trap, `.update()` for is_active. No flake risk seen; MD5 hasher in
   test settings keeps the 20-request throttle test fast.

## Score: 6.5 / 10
Auth code itself is careful and would score ~9. C1 is a hard deploy blocker that the green suite
structurally cannot detect; H1 is a real gap in the stated revocation invariant. Both are cheap.

## Unresolved questions
1. Has 0075 ever been executed against a DB where the DOT tables exist (prod dump / old-commit
   `migrate oauth2_provider`)? If yes with success, FK checks must have been off — confirm how.
2. Is admin-side password reset (Django admin / `changepassword`) an actual operator workflow here?
   Decides H1 priority.
3. Confirm `DJANGO_NUM_PROXIES=1` is set in the live env file, not only in the guide (M2).
