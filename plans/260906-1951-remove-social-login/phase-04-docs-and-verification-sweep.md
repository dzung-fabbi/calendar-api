# Phase 04 — Docs, deployment notes, final verification sweep

**Priority:** P2 · **Status:** complete · **Effort:** 30m · **Blocked by:** phases 02 and 03

Update the four docs that still describe social login, write the upgrade/ops note for a
destructive migration, and run the sweep that proves nothing social survived.

## Context links

- [plan.md](plan.md) · [phase-01](phase-01-remove-social-wiring-and-token-shim.md) ·
  [phase-02](phase-02-auth-endpoint-regression-tests.md) ·
  [phase-03](phase-03-drop-social-django-tables-migration.md)
- `~/.claude/rules/documentation-management.md`

## Key insights (grep-verified doc hits)

- `docs/api-reference.md:12-19` — the auth section. L12 says the endpoints come "từ
  `drf_social_oauth2.urls`"; L17 documents `POST /auth/convert-token` as *the* endpoint
  mobile/web clients use for social login; L19 documents `/auth/login/{provider}/`. Both
  rows must go.
- `docs/system-architecture.md:5` — "MySQL 5.7 storage; OAuth2 / social auth for
  authenticated endpoints."
- `docs/codebase-summary.md` — **no social login mention**. Its only `oauth`-ish line is
  L159 (FCM's TTL-cached Google service-account token) which is **unrelated and stays**.
  The change needed here is additive: the auth endpoints + the new
  `djangopj/auth_token_views.py` module are not listed anywhere yet.
- `docs/deployment-guide.md` — has a per-phase "Upgrading to phase N" convention
  (L7 "Upgrading to phase 6", L112 "Upgrading to phase 8"), each a numbered
  build → `migrate` list. Follow that shape.
- Docs are written in Vietnamese (`api-reference.md`) / English (the rest). Match each
  file's existing language; do not translate.

## Requirements

**Functional**
- No doc claims Facebook/Google login exists.
- `api-reference.md` auth table lists exactly `POST /auth/token` and
  `POST /auth/revoke-token`, states the optional trailing slash and that **both
  form-encoded and JSON bodies** are accepted.
- `deployment-guide.md` has an "Upgrading: social login removal" section covering image
  rebuild, mandatory backup, the migration, env cleanup, and the orphaned-account
  consequence.

**Non-functional**
- Concise. No changelog-style prose duplicating the plan (DRY — the plan folder is the
  history).

## Related code files

**Modify**
- `docs/api-reference.md` (L12-19)
- `docs/system-architecture.md` (L5, plus a one-line mention of `djangopj/auth_token_views.py`)
- `docs/codebase-summary.md` (add the two auth routes + the shim module)
- `docs/deployment-guide.md` (new section)

**Create / Delete**: none.

## Implementation steps

1. **`docs/api-reference.md`** — replace L12-19 with:
   - lead-in: endpoints served by `djangopj/auth_token_views.py` on top of
     django-oauth-toolkit, mounted at `/auth/`, trailing slash optional;
   - table rows: `POST /auth/token` (grant `password` and `refresh_token`) and
     `POST /auth/revoke-token` (logout);
   - one bullet: body may be `application/x-www-form-urlencoded` **or** JSON;
   - one bullet: `/auth/convert-token`, `/auth/login/{provider}/`, `/auth/authorize`,
     `/auth/invalidate-sessions`, `/auth/disconnect-backend` were **removed** and now
     return 404 — **đăng nhập Facebook/Google không còn được hỗ trợ**.
2. **`docs/system-architecture.md`** — L5 "OAuth2 / social auth" → "OAuth2
   (django-oauth-toolkit, `grant_type=password`)". Add one line near the layer/dir listing:
   `djangopj/auth_token_views.py` — DRF shim for `/auth/token` + `/auth/revoke-token`,
   exists because DOT's own views are form-encoded only (link phase-01 rationale).
3. **`docs/codebase-summary.md`** — add a short "Auth (`/auth/`)" table with the two routes
   and their view module. Leave L159 (FCM/google-auth) alone.
4. **`docs/deployment-guide.md`** — append a section in the house style:

   ```
   ## Upgrading: social login removal

   Facebook/Google login is gone. `/auth/token` and `/auth/revoke-token` are unchanged
   for clients (same URLs, optional trailing slash, form or JSON body).

   1. BACK UP FIRST: `mysqldump ... > backup-YYYYMMDD.sql`. Step 3 is IRREVERSIBLE.
   2. Rebuild the image -- `requirements.txt` changed (three social packages and three
      of their transitives removed): `docker compose build web`.
   3. `docker compose run --rm web python manage.py migrate giapha` -- applies `0007`,
      which DROPs social_auth_usersocialauth / _nonce / _association / _code / _partial.
      Run the orphan-account query in the note below BEFORE this step.
   4. Delete `SOCIAL_AUTH_FACEBOOK_KEY|SECRET` and `SOCIAL_AUTH_GOOGLE_OAUTH2_KEY|SECRET`
      from `.env` and the deployment secret store, and revoke the apps at Facebook for
      Developers / Google Cloud Console. They are in the git history -- treat as
      compromised regardless.
   5. Smoke test: `curl -sf -X POST https://HOST/auth/token -d grant_type=password -d ...`
      and the same call with `-H 'Content-Type: application/json'`.

   ### Consequence: social-only accounts can no longer log in

   Users who ever only signed in with Facebook or Google still exist in `auth_user`, but
   with an unusable password (`password` empty or starting with `!`). After this upgrade
   they have NO way to authenticate -- their data is intact, their login is not.
   Export them BEFORE step 3 (afterwards the link is gone):

   ```sql
   SELECT u.id, u.username, u.email, s.provider
   FROM auth_user u
   JOIN social_auth_usersocialauth s ON s.user_id = u.id
   WHERE u.password = '' OR u.password LIKE '!%';
   ```

   Recovery path for those accounts, cheapest first:
   - `manage.py changepassword <username>` (admin-set, then tell the user) or set one via
     `/admin/auth/user/`;
   - if the email on file is trustworthy, a standard Django password-reset email;
   - otherwise the user re-registers and an admin re-binds their `ClanMember` row.
   ```
5. Run the verification sweep (below) and paste nothing into the docs — it is a gate, not
   an artefact.

## Verification sweep (the gate for the whole plan)

```sh
# 1. no social reference outside plans/ and docs/
grep -rniE "facebook|social_auth|social_django|drf_social|social_core|social-auth" \
  --exclude-dir=.git --exclude-dir=plans --exclude-dir=docs .        # -> empty

# 2. docs mention social ONLY as removed-history
grep -rniE "facebook|social" docs/                                    # -> review by eye

# 3. django sanity
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py makemigrations --check --dry-run   # -> No changes detected

# 4. no social package in the rebuilt image
docker compose run --rm web pip list | grep -iE "social|openid|requests-oauthlib|defusedxml"  # -> empty

# 5. full suite, both apps together
./scripts/run-tests.sh
```

## Todo list

- [x] `docs/api-reference.md` auth section rewritten
- [x] `docs/system-architecture.md` L5 + shim module line
- [x] `docs/codebase-summary.md` auth routes added
- [x] `docs/deployment-guide.md` upgrade + consequence section
- [x] Sweep steps 1-5 all clean (**confirmed: 738 tests pass, 7 skipped; manage.py check clean; makemigrations clean**)

## Success criteria

- Sweep step 1 returns zero lines. ✓
- `makemigrations --check --dry-run` reports no changes (proves the model state matches the
  DB after phase 03). ✓
- `./scripts/run-tests.sh` green for `apis giapha` in one invocation. ✓ **738 tests pass, 7 skipped**
- A reader of `docs/api-reference.md` can call `/auth/token` correctly with either body
  type without reading any code. ✓

## Risk assessment

| Risk | L×I | Mitigation |
|---|---|---|
| Docs updated but an SDK/mobile app still calls `/auth/convert-token` | Med×High | Sweep cannot see client repos. **Open question below** — confirm with the mobile team before deploying; the 404 is silent from the server's side. |
| Sweep step 1 blocked by a false positive in `sao.txt`/`sao1.txt` or snapshots | Low×Low | Inspect the hit; only `.py`/config hits matter. |
| Deployment guide followed without the backup step | Low×High | Backup is step 1 and the section leads with "IRREVERSIBLE". |
| Vietnamese/English mixed into the wrong file | Low×Low | Match each file's existing language. |

## Security considerations

- The upgrade note tells operators to **revoke** the FB/Google app credentials, not just
  delete the env vars — they are in the git history (`.env.example` header already says
  committed secrets must be rotated).
- The orphan-account export is PII; the doc must say to delete it after use.

## Rollback

Docs-only phase — `git revert`. Note that reverting the docs does **not** restore
social login; phase 03's migration is the irreversible part.

## Open questions (not blocking release)

From the code review unresolved list:
1. **Deploy sequencing of `0007` migration.** Standard practice: release N = code, release N+1 = drop after soak. Currently `migrate` applies it inline. Decision pending.
2. **Dry-run the migration against a production dump** — test suite cannot exercise it (`IF EXISTS` no-ops on fresh DB).
3. **Throttling `/auth/token`.** Endpoint now the only login flow, remains unthrottled. Requires correct `NUM_PROXIES` setting to be meaningful.
4. **Pre-flight orphan-account query.** How many social-only accounts exist in production? The query in the deployment guide answers it; if zero, the breaking-change risk is minimal.
5. **Confirm no shipped client still calls `/auth/convert-token`** before the deploy window.
