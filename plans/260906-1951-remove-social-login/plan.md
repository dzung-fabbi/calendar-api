---
title: "Remove Facebook + Google social login"
description: "Strip drf-social-oauth2/social-auth from the project, keep /auth/token working unchanged, drop the social_django tables."
status: in-progress
priority: P2
effort: 3h
branch: master
tags: [auth, cleanup, oauth2, migration, breaking-change]
created: 2026-09-06
---

# Remove Facebook + Google Social Login

Delete every social-login dependency (`drf-social-oauth2`, `social-auth-app-django`,
`social-auth-core`) and its config/URL/table footprint. **`django-oauth-toolkit` stays** —
`grant_type=password` is the only login flow that survives.

## Non-negotiable constraint

`POST /auth/token` and `POST /auth/revoke-token` MUST keep working at the same URLs, with
the same optional trailing slash, and MUST keep accepting **both** form-encoded and JSON
bodies. Shipped mobile clients cannot be changed. DOT's own views are form-only → a thin
local shim (`djangopj/auth_token_views.py`) is required. See phase 01.

Endpoints deliberately dropped (will 404): `/auth/convert-token`, `/auth/authorize`,
`/auth/invalidate-sessions`, `/auth/invalidate-refresh-tokens`, `/auth/disconnect-backend`,
`/auth/login/{provider}/`, `/auth/complete/{backend}/`.

## Phases

| # | Phase | Status | Effort | Blocked by |
|---|---|---|---|---|
| 01 | [Remove social wiring + token compat shim](phase-01-remove-social-wiring-and-token-shim.md) | complete | 1h | — |
| 02 | [Auth endpoint regression tests](phase-02-auth-endpoint-regression-tests.md) | complete | 1h | 01 |
| 03 | [Drop social_django tables (migration)](phase-03-drop-social-django-tables-migration.md) | migration written 2026-09-09, **not yet applied** (needs backup + migrate) | 30m | 01 |
| 04 | [Docs + deployment notes + final sweep](phase-04-docs-and-verification-sweep.md) | complete | 30m | 02, 03 |

02 and 03 may run in parallel (disjoint files). 04 last — it asserts the whole thing.

## File ownership (no overlap between phases)

- **01**: `djangopj/settings.py`, `djangopj/urls.py`, `djangopj/auth_token_views.py` (new), `requirements.txt`, `docker-compose.yml`, `.env.example`
- **02**: `giapha/tests/test_auth_token_endpoints.py` (new)
- **03**: `giapha/migrations/0007_drop_social_auth_tables.py` (new)
- **04**: `docs/api-reference.md`, `docs/system-architecture.md`, `docs/codebase-summary.md`, `docs/deployment-guide.md`

## Key dependencies / facts

- No application code imports social packages. Only `djangopj/settings.py` + `djangopj/urls.py`
  reference them (verified by repo-wide grep; results in phase 01).
- `drf_social_oauth2.backends.DjangoOAuth2` calls `reverse('drf:token')` at *class-body*
  (import) time → the backend and the URL include MUST be removed in the same commit.
- KEEP, unrelated to login: all `FIREBASE_*` settings, `giapha/services/fcm.py`,
  `giapha/services/fcm_auth.py`, `google-auth`, `rsa`, `pyasn1`, the `googleapis.com` FCM
  scope string, `django-oauth-toolkit`, `oauthlib`, `jwcrypto`, `PyJWT`, `cryptography`.
- Latest giapha migration is `0006_visibility_public_link` → new one is `0007_*`.
- Tests run in docker only: `./scripts/run-tests.sh` (rebuilds `Dockerfile.test`, so a
  `requirements.txt` change is picked up automatically).

## Outstanding (deliberately not done)

(a) **`0007` table-drop migration — DECIDED, deferred.** Release N (this one) ships code only; the five `social_auth_*` tables stay in place, orphaned and harmless. Release N+1 adds the migration (source kept verbatim in phase-03) after a soak and a dry-run against a production dump. (b) **`/auth/token` throttling** — endpoint now the only login flow, remains unthrottled. Requires `NUM_PROXIES` set correctly. (c) **Pre-flight orphan-account query** — production dump needs dry-run before real deploy; test suite cannot exercise it (`IF EXISTS` no-ops on fresh DB).

## Breaking change to announce

Accounts created **only** via Facebook/Google keep existing in `auth_user` but have an
unusable password → after this release they cannot log in at all. This is true from the
CODE deploy, independently of the deferred table drop. `docs/deployment-guide.md`
documents the recovery paths; the pre-flight query there still has to run before release
N+1 drops the table that answers it.
