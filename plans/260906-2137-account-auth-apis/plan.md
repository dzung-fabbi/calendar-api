# Account & Authentication APIs

## Context

`calendar-api` has login and logout, but nothing else an account needs. Today:

- `POST /auth/token` (OAuth2 `password` / `refresh_token` grant) and `POST /auth/revoke-token` — the hand-written shim at `djangopj/auth_token_views.py`. **Working, shipped, must not change.**
- `GET /api/get-user` — read-only `me` (`apis/views/account.py::UserAPIView`).

There is **no** way to register, no way to recover a forgotten password, no way to change a password, and no way to edit a profile. Accounts can only be created by an admin (`createsuperuser` / Django admin). Worse, the Facebook/Google removal (commit `03687ef`) left users with `set_unusable_password()` and, per `docs/deployment-guide.md:274-276`, *no reset path at all* — the documented recovery is "an admin sets a password and tells them what it is".

This plan adds the five missing endpoints on top of the existing OAuth2 flow, and configures outbound email (of which the project currently has **none** — no `EMAIL_BACKEND`, no `send_mail` anywhere).

### Confirmed decisions

| Decision | Choice |
|---|---|
| Login / logout | **Unchanged.** `/auth/token` + `/auth/revoke-token` are not touched. |
| Identity | Email is the identity: `username = email`. Active immediately, no verification step. |
| Password recovery | 6-digit **OTP by email**. Real SMTP via env vars. |
| Profile fields | `first_name`, `last_name` + new `phone`, `birth_date`, `avatar_url`. |
| Avatar | Plain `avatar_url` field. Client uploads elsewhere. **No S3 code** — `giapha/services/storage.py` is *not* duplicated. |
| Email change | **Out of scope** — email is the login identity and `auth_user.email` is not unique. |
| After password change/reset | **Revoke every** OAuth2 access + refresh token. User re-logs in everywhere. |
| Legacy social accounts | **Can reset.** Do *not* gate on `has_usable_password()`. |

## Non-negotiable constraints

1. `POST /auth/token` and `POST /auth/revoke-token` keep working byte-for-byte. Nothing in `djangopj/` changes except `settings.py`.
2. **`apis/` must never import `giapha/`** (`docs/code-standards.md` → Decoupling). Everything here lands in `apis/`.
3. Every new endpoint gets a row in `apis/tests/test_query_counts.py` — the ceiling is a contract.
4. `python manage.py makemigrations apis --check --dry-run` must be clean after the one deliberate migration.
5. Response envelope `{"data": ...}`; 400s are the raw DRF error dict; `detail` prose is Vietnamese, codes/slugs are ASCII.

## Endpoints

| Method | Path | Auth | Body | Success |
|---|---|---|---|---|
| `POST` | `/api/auth/register` | — | `email`, `password`, `first_name?`, `last_name?` | `201 {"data": {user}}` |
| `POST` | `/api/auth/forgot-password` | — | `email` | `200 {"data": {"detail": "..."}}` — **always**, even for unknown emails |
| `POST` | `/api/auth/verify-otp` | — | `email`, `code` | `200 {"data": {"valid": true}}` — does not consume the code |
| `POST` | `/api/auth/reset-password` | — | `email`, `code`, `new_password` | `200 {"data": {"detail": "..."}}` |
| `POST` | `/api/auth/change-password` | Bearer | `current_password`, `new_password` | `200 {"data": {"detail": "..."}}` |
| `GET` | `/api/me` (+ existing `/api/get-user`) | Bearer | — | `200 {"data": {user + profile}}` |
| `PATCH` | `/api/me` (+ existing `/api/get-user`) | Bearer | `first_name?`, `last_name?`, `phone?`, `birth_date?`, `avatar_url?` | `200 {"data": {user + profile}}` |

`me` is a **second route onto the existing `UserAPIView`**, not a new view — `/api/get-user` stays for shipped clients, `me` is the name new clients should use. One view, one serializer, zero duplication.

`verify-otp` exists so the app can show "wrong code" on the code screen before asking for a new password. It validates without consuming.

## Design

### OTP storage — `PasswordResetCode`

A dedicated model, **not** `django.contrib.auth.tokens.default_token_generator`. That generator produces a long URL-safe token derived from the password hash and is stateless — it cannot express a 6-digit code, a per-code attempt counter, or single-use semantics, all of which are the actual security controls here.

```
user        FK(User, CASCADE, related_name='password_reset_codes')
code_hash   CharField(64)                 # HMAC-SHA256 hex
created_at  DateTimeField(auto_now_add, db_index)
expires_at  DateTimeField()
attempts    PositiveSmallIntegerField(0)
used_at     DateTimeField(null=True)
```

**Hashing: HMAC-SHA256 keyed on `SECRET_KEY`, not `make_password`.** Two reasons. A 6-digit code has only 10⁶ possible values, so a slow password hash buys nothing against anyone holding the table — but an HMAC key that lives *outside* the database means a DB-only leak yields nothing at all. And `djangopj/settings_test.py:41` swaps in `MD5PasswordHasher`, so `make_password` would be tested under a hasher production never uses. Compare with `hmac.compare_digest`.

Rules: TTL 10 minutes; single-use (`used_at`); max 5 attempts per code; requesting a new code marks every prior unused code for that user as used, so only the newest works.

### Email

`djangopj/settings.py` gains, using the existing `env_flag` helper (settings.py:22):

```
EMAIL_BACKEND = smtp if EMAIL_HOST else console   # dev/CI never breaks
EMAIL_HOST / EMAIL_PORT (587) / EMAIL_HOST_USER / EMAIL_HOST_PASSWORD
EMAIL_USE_TLS (default True) / DEFAULT_FROM_EMAIL
EMAIL_TIMEOUT = 10        # a hung SMTP server must not pin a gunicorn worker
PASSWORD_RESET_CODE_TTL_SECONDS = 600
PASSWORD_RESET_MAX_ATTEMPTS = 5
```

`djangopj/settings_test.py` forces the **locmem** backend so tests read `django.core.mail.outbox`.

Sending lives in `apis/services/mailer.py`. Services may do I/O but not ORM — the same licence `giapha/services/fcm.py` uses. An SMTP failure is logged and swallowed: it must not 500, and it must not let a caller tell a registered email from an unregistered one.

### Token revocation

`apis/selectors/auth_tokens.py::revoke_all_tokens(user)`, called on both reset and change, inside the same `transaction.atomic()` as the `set_password`.

Verified against the installed django-oauth-toolkit 2.2.0 (`oauth2_provider/models.py:423-485`):

- `RefreshToken.access_token` is a `OneToOneField(..., on_delete=SET_NULL)`, so deleting access tokens does **not** cascade to refresh tokens — it only nulls the pointer and leaves the refresh token alive.
- `RefreshToken.revoke()` *marks* `revoked` rather than deleting, and `Meta.unique_together = ("token", "revoked")` makes bulk revocation by that method awkward.
- There is no `token_family` in this version.

So **delete, in this order** — refresh tokens first, so nothing can mint a replacement mid-operation:

```python
from oauth2_provider.models import get_access_token_model, get_refresh_token_model

get_refresh_token_model().objects.filter(user=user).delete()
get_access_token_model().objects.filter(user=user).delete()
```

OIDC `IDToken` rows are not deleted: the project configures no `OAUTH2_PROVIDER` block and issues none. Add it here if OIDC is ever switched on.

### Profile fields

Added to the existing `UserProfile` (`apis/models/booking.py:62-71`, already auto-created for every user by the `post_save` signal at line 71):

- `phone` — `CharField(max_length=20, blank=True)`, validated against a Vietnamese mobile format in the serializer.
- `birth_date` — `DateField(null=True, blank=True)`, must not be in the future.
- `avatar_url` — `URLField(max_length=500, blank=True)`. **Client-supplied, so restrict the scheme to `http`/`https`** — a stored `javascript:` or `data:` URL is echoed to every other client that renders it.

`is_free` and `expiry_datetime` are billing internals and stay **off** the response. One migration: `apis/migrations/0073_account_profile_and_password_reset.py`.

`me` must `select_related('profile')` — the query-count test is a contract.

**A profile row is not guaranteed to exist.** `UserProfile` arrived in migration `0055`, and the `post_save` signal only fires on *creation* — so every account older than that migration has no profile row. This is a known condition in this codebase, not a hypothetical: `apis/admin/site_config.py:52` guards with `hasattr(el.user, 'profile')`, and its docstring records a past bug from getting exactly this wrong. A bare `user.profile` in the serializer raises `RelatedObjectDoesNotExist` → **500 on `me` for the oldest accounts**.

Handle it in both directions: `GET` serializes a missing profile as empty/null values rather than failing, and `PATCH` uses `UserProfile.objects.get_or_create(user=...)` inside the transaction. Cover a profile-less user explicitly in the tests.

## Security analysis

| Risk | Handling |
|---|---|
| **Enumeration via forgot-password** | Identical `200` body and comparable timing whether or not the email exists. Never reveal in the response that no account was found. |
| **Enumeration via register** | Unavoidable — "email already taken" is the error. Accepted, throttled, documented. |
| **OTP brute force** | 10⁶ keyspace. Per-code `attempts` cap of 5 is the *real* defence; IP throttles are secondary because `NUM_PROXIES=0` (settings.py:189) means per-IP buckets fall back to `REMOTE_ADDR` and a botnet defeats them. Exhausting attempts burns the code. |
| **Weak passwords** | `django.contrib.auth.password_validation.validate_password` on register, reset, and change. `AUTH_PASSWORD_VALIDATORS` is already configured (settings.py:114-127). |
| **Stolen session survives a reset** | All tokens revoked on both reset and change. |
| **Concurrent register, same email** | `auth_user.username` is unique; the DB decides. Catch `IntegrityError` **inside `with transaction.atomic()`** (`docs/code-standards.md` → Errors) and return the same 400 as the serializer check. |
| **Password/OTP in logs** | Codes and passwords are `write_only`; never echo the OTP in a response body; never log it. |
| **Legacy unusable-password accounts** | Deliberately allowed to reset — possession of the mailbox is the proof. This retires the caveat at `docs/deployment-guide.md:274-276`. |

Throttle scopes added to `REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']` (joining the existing `giapha-join` / `giapha-public`): `auth-register` 10/hour, `auth-forgot-password` 5/hour, `auth-reset-password` 10/hour, `auth-change-password` 10/hour. Per-view `throttle_scope` opt-in only — no project-wide default (that would change behaviour for every existing endpoint).

## Files

**New**
- `apis/models/password_reset.py`, `apis/migrations/0073_account_profile_and_password_reset.py`
- `apis/services/otp.py` (pure: generate via `secrets`, HMAC, constant-time compare), `apis/services/mailer.py`
- `apis/selectors/password_reset.py`, `apis/selectors/auth_tokens.py`
- `apis/serializers/auth.py`, `apis/serializers/profile.py`
- `apis/views/auth_register.py`, `apis/views/auth_password.py`
- Tests: `apis/tests/test_auth_register_api.py`, `test_auth_password_reset_api.py`, `test_auth_change_password_api.py`, `test_profile_api.py`

**Modified**
- `apis/models/booking.py` (3 profile fields), `apis/models/__init__.py`, `apis/serializers/__init__.py`, `apis/views/__init__.py` — flat re-exports, per `docs/code-standards.md` → Files
- `apis/serializers/account.py` (nest profile), `apis/views/account.py` (add `patch`), `apis/urls.py`
- `djangopj/settings.py`, `djangopj/settings_test.py`, `.env.example`
- `apis/tests/test_query_counts.py`, `apis/tests/test_security.py`, `apis/tests/factories.py`
- `docs/api-reference.md` (new "Tài khoản & Xác thực" section), `docs/codebase-summary.md` (endpoint table ~line 21), `docs/deployment-guide.md` (retire the no-reset caveat), `docs/system-architecture.md`

No new dependencies — `requirements.txt` is unchanged. Every module stays under 200 lines.

## Phases

| # | Phase | Status | Blocked by |
|---|---|---|---|
| 01 | Email config + settings + `.env.example` | complete | — |
| 02 | Models, migration, OTP + mailer services, selectors | complete | — |
| 03 | Register + password endpoints (serializers, views, urls) | complete | 01, 02 |
| 04 | Profile `me` GET/PATCH | complete | 02, 03 |
| 05 | Tests | complete | 03, 04 |
| 06 | Docs | complete | 05 |
| 07 | Giapha clan-roster username gate (regression found during 05) | complete | 03 |

**Phase 07 was not in the original plan.** Registration storing the email as
`username` voided the owner-only `email` gate in
`giapha/serializers/clan.py::ClanMemberSerializer` -- the roster is readable by any clan
member, so a viewer would have harvested every member's address from the ungated
`username` field. Fixed by gating `username` alongside `email` and adding `display_name`.
Breaking change for giapha clients; documented at the top of `docs/api-reference.md`.

01 and 02 are disjoint and may run in parallel. **03 and 04 must be sequential** — both touch `apis/urls.py`, `apis/views/__init__.py`, `apis/serializers/__init__.py`.

Plan directory: `plans/260906-2137-account-auth-apis/`.

## Verification

```sh
./scripts/run-tests.sh apis            # new + existing apis suite
./scripts/run-tests.sh                 # apis + giapha together (shared auth_user AUTO_INCREMENT)
docker compose run --rm web python manage.py makemigrations apis --check --dry-run
```

The full suite matters, not just `apis`: `scripts/run-tests.sh` documents that both apps share `auth_user`, so adding user-creating tests can make `giapha`'s suite order-dependent.

End-to-end against a running stack (`docker-compose up -d`), with `EMAIL_HOST` unset so the console backend prints the OTP to the log:

1. `POST /api/auth/register` → 201; re-post the same email → 400.
2. `POST /auth/token` with `grant_type=password` → access token. **Proves registration produces a user the existing, untouched login flow accepts** — the single most important check here.
3. `GET /api/me` with the bearer token → 200, profile nested, no `password` / `is_free` / `expiry_datetime`.
4. `PATCH /api/me` → phone, birth date, avatar URL persist. Send `avatar_url: "javascript:alert(1)"` → 400.
5. `POST /api/auth/forgot-password` → 200; read the code from the log. Post an unknown email → byte-identical 200.
6. `POST /api/auth/reset-password` with a wrong code 5× → locked out; a 6th attempt with the *correct* code still fails.
7. New code → `reset-password` succeeds → the token from step 2 now 401s, and `/auth/token` works with the new password.
8. `POST /api/auth/change-password` while authenticated → 200, and that token 401s afterwards.

Regression: `giapha/tests/test_auth_token_endpoints.py` must stay green untouched.

## Outcome

805 tests pass (`./scripts/run-tests.sh`, `apis` + `giapha` together). `makemigrations
--check --dry-run` clean for both apps. `get-user` stayed at a 1-query budget despite
gaining the nested profile.

Deviations from the plan as approved:

- `apis/views/auth_password.py` reached 222 lines, so it was split into
  `auth_password_reset.py` and `auth_password_change.py` (the 200-line rule). The shared
  write moved to `apis/selectors/auth_tokens.py::set_password_and_revoke_tokens`.
- Added beyond the plan, all security-driven: a per-user cap of 3 reset requests/hour;
  `is_active` filtering on the reset lookup (a banned account must not be recoverable by
  mailbox possession); the OTP hash bound to the user id; rejection of non-BMP characters
  in names (MySQL 5.7 here is 3-byte `utf8`, so an emoji was a 500); `new_password` must
  differ from `current_password`; opportunistic cleanup of codes older than a day.
- `test_query_counts.py`'s helper was GET-only and had no entry for `get-user` at all,
  despite `docs/codebase-summary.md` publishing a budget for it. Extended for POST/PATCH
  and the missing entry added.

## Open questions

1. `phone` validation accepts 8-15 digits with an optional `+`. Tighten to strict
   Vietnamese mobile prefixes (`0[35789]xxxxxxxx`) if international numbers are not wanted.
2. Throttle state is per-process (`LocMemCache`, no `CACHES` setting), so every rate is
   effectively multiplied by the worker count. Pre-existing and it also affects
   `giapha-join`/`giapha-public`; a shared cache backend is separate work.
3. Legacy rows where `username != email` (social-era accounts) still cannot use the reset
   flow. Worth running `SELECT COUNT(*) FROM auth_user WHERE username <> email` against a
   production dump to size that group.
