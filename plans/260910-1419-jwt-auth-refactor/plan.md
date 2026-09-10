---
title: "Replace django-oauth-toolkit with in-house JWT auth"
description: "Drop OAuth2 client_id/client_secret entirely; issue PyJWT HS256 access tokens + hashed opaque refresh tokens from three new /api/auth/* endpoints."
status: completed
priority: P1
effort: 5h30m
branch: master
tags: [auth, jwt, oauth2, breaking-change, migration, cleanup]
created: 2026-09-10
completed: 2026-09-10
---

# In-house JWT auth, django-oauth-toolkit removed

`django-oauth-toolkit` (DOT) goes away completely — package, app, tables, the
`client_id`/`client_secret` concept, and `djangopj/auth_token_views.py`. Login becomes
username/password against three new endpoints in `apis/`. Access = PyJWT HS256 (already
pinned, `PyJWT==2.6.0`); refresh = opaque `secrets` token stored **sha256-hashed** in a new
`apis.RefreshToken` row. No new dependency. `simplejwt` is out of scope by decision.

## Breaking change (accepted)

`POST /auth/token` and `POST /auth/revoke-token` are **deleted** (404 after deploy). Every
shipped client must move to `/api/auth/login|refresh|logout` and stop sending
`client_id`/`client_secret`. Every live access and refresh token dies at deploy: all users
log in again. Announce with the release.

## New wire contract

| Endpoint | Body | Success |
|---|---|---|
| `POST /api/auth/login` | `username`, `password` | 200 `{access_token, refresh_token, token_type:"Bearer", expires_in}` |
| `POST /api/auth/refresh` | `refresh_token` | 200, same shape, **rotated** (old row deleted) |
| `POST /api/auth/logout` | `refresh_token` | 204, empty body |

Bad credentials / inactive user / bad-expired-unknown refresh token → **401** with one
generic message (no enumeration). Missing field → 400 field errors. Payload is flat, **not**
`{"data": ...}`-wrapped — same as the old token endpoint.

## Phases

| # | Phase | Status | Effort | Blocked by |
|---|---|---|---|---|
| 01 | [Token core: settings, model, services, auth class](phase-01-token-core-model-services-authentication.md) | ✅ completed | 1h30m | — |
| 02 | [Login / refresh / logout endpoints](phase-02-auth-endpoints-login-refresh-logout.md) | ✅ completed | 1h | 01 |
| 03 | [Remove DOT: app, package, tables](phase-03-remove-django-oauth-toolkit.md) | ✅ completed | 45m | 02 |
| 04 | [Tests: rewrite the two DOT-bound suites](phase-04-tests-rewrite-auth-suites.md) | ✅ completed | 1h30m | 03 |
| 05 | [Docs sweep](phase-05-docs-sweep.md) | ✅ completed | 45m | 04 |

**All phases completed.** Full test suite green: 856 tests, 0 failed, 7 skipped.
`pip check` clean. `manage.py check` + `makemigrations --check --dry-run` clean.

## File ownership (no overlap)

- **01**: `djangopj/settings.py` (JWT block + `DEFAULT_AUTHENTICATION_CLASSES`), `.env.example`,
  `apis/models/refresh_token.py` + `__init__.py`, `apis/migrations/0074_*`,
  `apis/services/jwt_tokens.py`, `apis/selectors/refresh_tokens.py`, `apis/selectors/auth_tokens.py`,
  `apis/authentication.py`
- **02**: `apis/views/auth_login.py` + `views/__init__.py`, `apis/serializers/auth.py`,
  `apis/urls.py`, `djangopj/urls.py`, `djangopj/settings.py` (throttle rates only),
  delete `djangopj/auth_token_views.py`
- **03**: `djangopj/settings.py` (`INSTALLED_APPS`, backend comment), `requirements.txt`,
  `apis/migrations/0075_drop_oauth2_provider_tables.py`
- **04**: `apis/tests/test_auth_login_api.py` (new), `apis/tests/test_auth_change_password_api.py`,
  `apis/tests/test_services.py`, `apis/tests/test_query_counts.py` +
  `apis/tests/snapshots/query_budgets.json`, delete `giapha/tests/test_auth_token_endpoints.py`
- **05**: `docs/api-reference.md`, `docs/codebase-summary.md`, `docs/system-architecture.md`,
  `docs/deployment-guide.md`, `README.md`

## Release checklist (OPEN — requires ops)

- **Before migrate:** `mysqldump` production database (irreversible 0075 drop)
- **Before deploy:** Verify `DJANGO_NUM_PROXIES=1` set in prod env (throttles now real)
- **Deploy sequence:** Image first, then `migrate` (0075 has `SET FOREIGN_KEY_CHECKS` wrapper)
- **Test migration:** Run migration against restored prod dump to verify circular FK handling
- **Announce breaking change:** Old `/auth/token` and `/auth/revoke-token` return 404; all users must re-login (all tokens invalidated at deploy)
- **Post-deploy:** Confirm login from two IPs returns 429 on 21st attempt (throttle validation)
- **Optional:** Set `JWT_SIGNING_KEY` to independent value; rotate independently of `DJANGO_SECRET_KEY`
