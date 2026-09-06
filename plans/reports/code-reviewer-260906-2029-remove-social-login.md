# Code review — remove Facebook/Google social login

Date: 2026-09-06 · Plan: `plans/260906-1951-remove-social-login/` · Branch: master (uncommitted)
Reviewer verified against upstream `drf-social-oauth2==2.1.1` source + live probes in
`calendar-api-test:latest`. Every finding below was reproduced, not inferred.

Final state: **738 tests pass, 7 skipped**. `manage.py check` clean, `makemigrations --check` clean.

## Verdict on the port

Faithful. URL regexes (`^token/?$`, `^revoke-token/?$`), serializer `max_length`s, the
`AccessToken.DoesNotExist` message string and the 204-on-empty-body rule all match upstream.
No app code ever imported the social packages.

## Findings and resolution

| # | Sev | Finding | Resolution |
|---|---|---|---|
| 1 | MAJOR | `renderer_classes = (JSONRenderer,)` made `Accept: text/html` return **406** where the old endpoint returned 200 (DRF default renderers include `BrowsableAPIRenderer`; project sets no `DEFAULT_RENDERER_CLASSES`). Silent unrecoverable login failure for any client sending that header. | **FIXED** — override removed, parity restored. Pinned by `test_token_accepts_every_accept_header` (4 Accept values). |
| 2 | MAJOR | Non-mapping JSON body (`[1,2,3]`, `"x"`, `null`, `42`) → `AttributeError` → **500** on an unauthenticated endpoint, at request rate. Same bug upstream, but ours now. | **FIXED** — `_copy_parsed_body_into_post` raises `ParseError` → 400. Pinned by `test_token_non_object_json_body_is_400_not_500`. |
| 3 | MAJOR | `sensitive_post_parameters` redacts `request.POST` but Django only cleanses variables whose *name* matches its regex — the plaintext password still reached traceback frame locals. Phase-01's "passwords stop appearing in error reports" was overstated. | **FIXED** — `@sensitive_variables` added on `post` and the helper. |
| 4 | MAJOR | Claimed the 204 revoke body changed from `""` to empty, losing `Content-Type`. | **PARTLY WRONG — verified.** Reviewer measured `JSONRenderer.render('')` in isolation. On the wire the body is empty either way: Django's `test/client.py:96 conditional_content_removal` strips 204 bodies, mirroring RFC 7230 §3.3.3 as real servers do. The **`Content-Type` half is real**, so upstream's `data=''` form was kept. Pinned by asserts on `b''` + header. |
| 5 | MAJOR | Irreversible `0007` table drop ships in the same release as the code → no rollback window. Migration is **never exercised by tests** (`IF EXISTS` no-ops on a fresh DB), so "suite green" says nothing about it. | **OPEN — ops decision.** See "Unresolved" below. |
| 6 | MINOR | `test_token_form_encoded_body` did not test form encoding — Django's test client defaults to `multipart/form-data`. Real `application/x-www-form-urlencoded` had no coverage. | **FIXED** — explicit `urlencode` + content type; separate `test_token_multipart_body` added. |
| 7 | MINOR | 401s dropped oauthlib's `WWW-Authenticate` (RFC 6749 §5.2 requires it). Upstream dropped it too. | **FIXED** — `_with_oauthlib_headers` copies them, never clobbering `Content-Type`. Pinned by `test_token_bad_client_secret_is_401_with_www_authenticate`. |
| 8 | MINOR | `/auth/token` is unthrottled and is now the **only** login flow → unlimited credential stuffing. Pre-existing; blast radius changed. Note `NUM_PROXIES=0` means any throttle added is `REMOTE_ADDR`-based until a real proxy count is set. | **OPEN — deliberate deferral.** Out of scope for a removal change; see below. |
| 9 | MINOR | Class-level `csrf_exempt` redundant — DRF's `APIView.as_view()` already applies it (proved via the doubled decorator chain in a traceback). | **FIXED** — removed, replaced by a comment. |
| 10 | MINOR | URL names `token` / `revoke-token` are global and collision-prone. | **FIXED** — `auth-token` / `auth-revoke-token`. Nothing reverses them. |
| 11 | MINOR | `OPTIONS /auth/token` publishes the view docstring. Upstream did the same. | **WONTFIX** — cosmetic; docstring is short and non-sensitive. |
| 12 | MINOR | `request._request.POST` left `_mutable=True` and now carries the plaintext password; would be logged by any request-logging middleware added later. | **DOCUMENTED** — comment in the helper. |
| 13 | MINOR | Plan files still `status: pending`. | **FIXED** — synced. |
| 14 | MINOR | Test lives in `giapha/tests/` but owns `djangopj/` URLs; `manage.py test apis` alone skips it. | **ACCEPTED** — deliberate, `run-tests.sh` defaults to `apis giapha`. Documented in the module docstring. |

Nits 15–17 (garbled comment, no `elidable=True`, missing rollback-after-drop note) — 15 fixed, 16/17 accepted.

## Things the review confirmed as correct

- Migration SQL: child-with-FK dropped first; `sqlmigrate` shows six separate statements;
  MySQL 5.7 `can_rollback_ddl=False` so Django correctly runs it non-atomically; idempotent.
- `authentication_classes = ()` is strictly more permissive, not a security regression —
  it stops a stale `Bearer` header from 401-ing a valid refresh.
- Decorator stacking on `dispatch` applies both, in the right order.
- `RevokeTokenView` error cases all unchanged: unknown token → 204, wrong secret → 401
  `invalid_client`, token >500 chars → 400 field error.
- Zero leftovers: grep for `facebook|social_auth|social_django|drf_social|social_core|drfso2`
  outside `.git`/`plans`/`.claude` hits only intentional prose. `pip list` confirms the six
  packages gone, `django-oauth-toolkit`/`oauthlib`/`jwcrypto` correctly retained.

## Unresolved questions

1. **Deploy sequencing of `0007` (#5).** Standard practice for an irreversible drop is
   release N = code, release N+1 = drop, after a soak. Currently `migrate` applies it inline.
   Split into a follow-up, or add an explicit soak banner to the deployment guide?
2. **Dry-run the migration against a production dump before the real deploy** — the test
   suite provably cannot cover it.
3. **Throttling `/auth/token` (#8)** — fix now or track separately? Requires setting
   `NUM_PROXIES` correctly to be meaningful at all.
4. **How many social-only accounts exist in production?** The pre-flight query in
   `docs/deployment-guide.md` answers it; if zero, #5 drops to minor.
5. **Is an error-reporting sink (ADMINS/Sentry) attached in production?** Sets the residual
   severity of #2/#3.
