# Phase 05 — Docs sweep

**Priority:** P2 · **Status:** completed · **Effort:** 45m · **Blocked by:** phase 04

## Context links

- [plan.md](plan.md) · previous: [phase-04](phase-04-tests-rewrite-auth-suites.md)
- Rules: `%USERPROFILE%/.claude/rules/documentation-management.md`;
  `docs/api-reference.md` is **Vietnamese** — keep it Vietnamese.

## Overview

OAuth2 is described in five documents and the README. Every mention of `client_id`,
`client_secret`, `grant_type`, `/auth/token` and `/auth/revoke-token` is now wrong. One of
those sections — the public-client runbook — is not merely stale but actively misleading,
and must be replaced rather than edited.

## Key insights

- **`docs/deployment-guide.md` L464-507 ("OAuth2 application is a `public` client") is
  obsolete in full.** It is an incident write-up whose fix (flip the Application row to
  `public`) is now impossible: the row and its table are gone. Replace the whole section
  with the JWT operational runbook. Keep the *date and reason* in one sentence so the
  history is not silently erased.
- **L508-513 ("Known gap: `/auth/token` is unthrottled") is now CLOSED** by phase 02's
  `auth-login`/`auth-refresh` scopes. Delete the gap, record the resolution, and keep the
  `DJANGO_NUM_PROXIES` caveat — it still applies to the new scopes.
- `docs/api-reference.md` has **four** places to touch, not one: the header table (L5-9), the
  whole "Xác Thực" section (L14-62 incl. the public-client warning), the envelope-exception
  list (~L66-70), the "Tài Khoản" intro + "Đăng ký" note (~L161, ~L192), and the throttling
  list (~L306).
- No `docs/project-changelog.md` and no `docs/development-roadmap.md` exist in this repo —
  nothing to append. Do not create them for this change.
- `docs/codebase-summary.md` L44-56 is a whole block describing `djangopj/auth_token_views.py`
  and its two routes; it is replaced by three rows in the `apis/` endpoint table above it
  (L21-38), not by a rewritten block.

## Requirements

- No occurrence of `client_id`, `client_secret`, `grant_type`, `oauth2_provider`,
  `django-oauth-toolkit`, `/auth/token` or `/auth/revoke-token` survives in `docs/` or
  `README.md`, except where a sentence deliberately records what was removed and when.
- The deployment guide tells an operator: what to set, what breaks at deploy, and how to log
  everyone out.
- Client-facing docs state the migration plainly: the old URLs 404; send `username`/`password`
  to `/api/auth/login`; drop the client fields entirely.

## Related code files

**Modify**
- `docs/api-reference.md` (Vietnamese) — L5-9, L14-62, ~L66-70, ~L161, ~L192, ~L306
- `docs/codebase-summary.md` — the `apis/` route table (add three rows) and L44-56 (delete the
  `djangopj/auth_token_views.py` block); the "Test suites" section (file list + counts)
- `docs/system-architecture.md` — L5-8 (intro sentence), L155-157 ("Account management"),
  L184-189 ("Both password-changing paths revoke every token")
- `docs/deployment-guide.md` — ~L384 area, and L455-513 (replace the public-client section,
  close the throttling gap)
- `README.md` L6 — "OAuth2 login" → "JWT login"

**Create / Delete** — none.

## Implementation steps

1. **`docs/api-reference.md`**
   - Header table row: `| Đăng nhập / đăng xuất (JWT) | /api/auth/ | app apis/ |`.
   - Rewrite "Xác Thực": keep `Authorization: Bearer {access_token}`, replace the endpoint
     table with the three routes and their bodies, and state:
     - access token là **JWT HS256**, mặc định sống 1 giờ (`expires_in` trong response);
     - refresh token là chuỗi ngẫu nhiên, lưu **băm sha256**, **dùng một lần** — mỗi lần
       refresh trả về token mới và huỷ token cũ;
     - sai mật khẩu / tài khoản bị khoá / refresh token hỏng-hết hạn-đã dùng → **401** với
       một thông báo chung (không phân biệt được, cố ý);
     - đổi mật khẩu làm **mọi access token hết hiệu lực ngay** (claim `pwd`), không chờ hết hạn;
     - thiếu field → 400; body chấp nhận cả form-encoded lẫn JSON.
   - **Delete** the entire "⚠️ Client là `public`" subsection (L36-62). Replace it with a short
     "Chuyển đổi từ `/auth/token` (BREAKING)" box: URL cũ trả 404; bỏ hẳn
     `client_id`/`client_secret`/`grant_type`; mọi người dùng phải đăng nhập lại sau khi deploy.
   - Envelope-exception list: add "ba endpoint `/api/auth/login|refresh|logout` trả payload
     phẳng, không bao `{"data": …}`".
   - "Tài Khoản" intro (~L161) and "Đăng ký" (~L192): `/auth/token` + `grant_type=password`
     → `/api/auth/login`.
   - Throttling list (~L306): replace the "kể cả `/auth/token`" bullet with
     `auth-login` 20/giờ, `auth-refresh` 60/giờ; note `logout` is unthrottled and why
     (a 256-bit token is not guessable).
2. **`docs/codebase-summary.md`**
   - Add to the `apis/` table: `auth/login` · `views/auth_login.py` · public POST, throttled;
     `auth/refresh` · same · public POST, throttled; `auth/logout` · same · public POST.
     Fill the Queries column from `query_budgets.json` (phase 04 measured them).
   - Delete the "auth endpoints (`djangopj/auth_token_views.py`…)" block.
   - Add one line under `apis/` describing `apis/authentication.py` +
     `apis/services/jwt_tokens.py` + `apis/models/refresh_token.py`.
   - Update the "Test suites" section: `test_auth_login_api.py` added,
     `giapha/tests/test_auth_token_endpoints.py` removed, and the headline test count
     re-recorded from the actual phase-04 run (do not guess it).
3. **`docs/system-architecture.md`**
   - L5-8: "OAuth2 (django-oauth-toolkit, `grant_type=password`)" → "in-house JWT (PyJWT
     HS256 access token + opaque, sha256-hashed refresh token)". Drop the paragraph about the
     shim living outside both apps; the endpoints now live in `apis/`.
   - L155-157: login/logout now `/api/auth/login|refresh|logout`.
   - L184-189: rewrite the revocation paragraph. New content: access tokens are **not stored**
     and are revoked by the `pwd` claim (sha256 of the password hash, first 16 hex chars), so
     a password change invalidates them instantly; refresh rows are **deleted**, never
     soft-revoked — the DOT soft-revoke trap that motivated this is worth one sentence of
     history so nobody reintroduces the shape.
   - Add a short note under Layers: `DEFAULT_AUTHENTICATION_CLASSES` points at
     `apis.authentication.JWTAuthentication` **as a settings string**, so `giapha/` still
     imports nothing from `apis/` and the decoupling rule holds.
4. **`docs/deployment-guide.md`**
   - Replace L464-507 with **"JWT auth (replaced OAuth2 on 2026-09-10)"**:
     - `JWT_SIGNING_KEY` — optional, falls back to `DJANGO_SECRET_KEY`; generate with
       `python -c "import secrets; print(secrets.token_urlsafe(48))"`; must be identical
       across all app containers or tokens minted by one are rejected by another;
     - `JWT_ACCESS_TOKEN_LIFETIME_SECONDS` (3600) / `JWT_REFRESH_TOKEN_LIFETIME_SECONDS`
       (2592000);
     - **at deploy every user must log in again** — both old and new tokens are invalidated;
     - **how to log everyone out on purpose:** rotate `JWT_SIGNING_KEY` **and**
       `DELETE FROM apis_refreshtoken;` — the key alone is not enough, because a surviving
       refresh row re-mints under the new key;
     - one sentence of history: the 2026-09-09 `public`-client fix is superseded; the
       `oauth2_provider_*` tables were dropped by `apis/migrations/0075_*`;
     - the `mysqldump`-before-`migrate` requirement, pointing at phase 03.
   - Replace "Known gap: `/auth/token` is unthrottled" with a resolved note naming
     `auth-login` 20/hour and `auth-refresh` 60/hour, and keep the `DJANGO_NUM_PROXIES`
     caveat (per-IP buckets are only meaningful once it matches the real proxy count).
   - Add an "abandoned refresh rows" line: rows are deleted on rotation and logout, so only
     abandoned sessions accumulate; prune with
     `DELETE FROM apis_refreshtoken WHERE expires_at < NOW();` if the table ever matters.
     No job ships for this — deliberate.
5. **`README.md`** L6: "for OAuth2 login" → "for JWT login (`/api/auth/login`)".
6. Final sweep:
   `grep -rni "client_secret\|client_id\|grant_type\|oauth2\|django-oauth-toolkit\|/auth/token\|revoke-token" docs README.md`
   → only the deliberate historical sentences remain.

## Todo list

- [x] `docs/api-reference.md` — six locations, Vietnamese, public-client section deleted
- [x] `docs/codebase-summary.md` — three route rows, old block deleted, module list, test counts re-recorded
- [x] `docs/system-architecture.md` — L5-8, L155-157, L184-189, decoupling note
- [x] `docs/deployment-guide.md` — public-client runbook replaced, throttling gap closed, prune note
- [x] `README.md` L6
- [x] Final grep clean

## Deviations from plan

1. **Five files updated** (all per the plan): `docs/api-reference.md`, `docs/codebase-summary.md`, `docs/system-architecture.md`, `docs/deployment-guide.md`, `README.md`.
2. **Additional follow-up edits**: Sections updated to reflect the circular FK fix (phase 03), password_fingerprint addition (phase 01), atomic refresh operation (phase 02), and throttle behaviour change (phase 02).

## Success criteria

- [x] The grep in step 6 returns only intentional history.
- [x] An operator can deploy from `docs/deployment-guide.md` alone: knows what to set, that all
  users are logged out, and how to force a mass logout later.
- [x] A mobile developer can migrate from `docs/api-reference.md` alone: three URLs, two bodies,
  one 401 rule, no client credentials anywhere.
- [x] Query counts in `codebase-summary.md` match `apis/tests/snapshots/query_budgets.json`.

## Risk assessment

| Risk | L×I | Mitigation |
|---|---|---|
| Line numbers drift after phases 01-04 land | **High**×Low | Locate by heading text, not by line number; the numbers here are a starting map |
| An English sentence slips into the Vietnamese reference | Med×Low | Copy the register of the surrounding text; the file is Vietnamese throughout |
| Deleting the public-client section erases useful incident history | Med×Low | One retained sentence with the 2026-09-09 date and outcome |
| Test counts copied from the old docs instead of the new run | Med×Low | Step 2 says re-record from the phase-04 run |

## Security considerations

- The deployment guide must **not** contain a real `JWT_SIGNING_KEY` example value — only the
  generator command, exactly as the `DJANGO_SECRET_KEY` entry does.
- Document the mass-logout procedure as key rotation **plus** truncating `apis_refreshtoken`;
  publishing only half of it would leave an operator believing they had evicted an attacker.
- State plainly that an access token cannot be revoked inside its lifetime except by a
  password change — an operator planning an incident response needs to know that.

## Next steps

Release: deploy the image first, then `migrate`, then announce the client-side breaking
change. Nothing in this plan remains after phase 05.
