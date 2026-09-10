# Phase 03 — Remove django-oauth-toolkit: app, package, tables

**Priority:** P1 · **Status:** completed · **Effort:** 45m · **Blocked by:** phase 02

## Context links

- [plan.md](plan.md) · previous: [phase-02](phase-02-auth-endpoints-login-refresh-logout.md)
  · next: [phase-04](phase-04-tests-rewrite-auth-suites.md)
- Migration pattern to copy **verbatim in shape**: `giapha/migrations/0007_drop_social_auth_tables.py`
- Ops history this obsoletes: `docs/deployment-guide.md` L464-507 (the public-client runbook)

## Overview

By now nothing in the code path uses DOT. Take it out of `INSTALLED_APPS` and
`requirements.txt`, and drop the five `oauth2_provider_*` tables plus their
`django_migrations` rows.

## Key insights

- **`INSTALLED_APPS` removal and the DROP must ship together but as two migrations.**
  `0074` (phase 01) creates `apis_refreshtoken`; `0075` drops the DOT tables. Separate files
  so a reviewer sees one reversible change and one irreversible one, and so `0075` can be
  held back if ops wants a soak (see Risk).
- **`DROP TABLE IF EXISTS` is load-bearing, not defensive style.** Once `oauth2_provider`
  leaves `INSTALLED_APPS` the test database never creates those tables, so a bare `DROP`
  fails **every** `./scripts/run-tests.sh` run forever. Same trap as `giapha/0007`.
- **Statements must go in as a list.** MySQLdb's `execute()` refuses more than one statement
  per string — `giapha/0007` documents this.
- **Drop order matters** (MySQL 5.7 enforces FKs on DROP): child tables first.
  `oauth2_provider_accesstoken` has a OneToOne to `oauth2_provider_idtoken`, so accesstoken
  must be dropped **before** idtoken — the intuitive alphabetical order is wrong.
- MySQL 5.7 `can_rollback_ddl = False`: Django will not wrap this in a transaction anyway,
  so no `atomic = False` is needed and the `DELETE` auto-commits.
- **Orphan dependencies.** Verified: no project source imports `oauthlib`, `jwcrypto`,
  `Deprecated`/`wrapt`, `cryptography`, `ecdsa` or `jose`. `oauthlib` + `jwcrypto` are
  DOT-only; `Deprecated`/`wrapt` are jwcrypto-only. `google-auth` (FCM) and `python-jose`
  stay per instruction — `python-jose` pulls `ecdsa`/`rsa`/`pyasn1`, so those stay too.
  `cryptography` stays: it is `python-jose`'s crypto backend extra and removing it is a
  separate, riskier decision.

## Requirements

**Functional**
- `oauth2_provider` gone from `INSTALLED_APPS`; `django-oauth-toolkit` and `oauthlib` gone
  from `requirements.txt`.
- Migration drops all five tables on a database that has them; clean no-op on one that
  never did; `django_migrations` has no `app='oauth2_provider'` rows afterwards.
- Reverse is a documented no-op.

**Non-functional**
- `pip check` inside the test image reports no broken requirements after the removals.
- Image build is not broken by the removed pins.

## Architecture

```
manage.py migrate
  apis.0074_refresh_token                  CREATE TABLE apis_refreshtoken      (reversible)
  apis.0075_drop_oauth2_provider_tables    DROP TABLE IF EXISTS x5             (IRREVERSIBLE)
                                           DELETE FROM django_migrations WHERE app='oauth2_provider'
```

Drop order (child → parent) — **NOTE: circular FK requires special handling**:

```
DOT 2.2.0 has a CIRCULAR FK:
  - oauth2_provider_refreshtoken.access_token_id → oauth2_provider_accesstoken (FK)
  - oauth2_provider_accesstoken.source_refresh_token_id → oauth2_provider_refreshtoken (OneToOne)
No drop order satisfies a cycle. Solution: wrap all DROP statements in
SET FOREIGN_KEY_CHECKS=0; ... DROP ...; SET FOREIGN_KEY_CHECKS=1;

Original plan (now incorrect):
  oauth2_provider_refreshtoken   FK -> accesstoken, application, auth_user
  oauth2_provider_accesstoken    FK -> idtoken (OneToOne), application, auth_user
  oauth2_provider_idtoken        FK -> application, auth_user
  oauth2_provider_grant          FK -> application, auth_user
  oauth2_provider_application    FK -> auth_user
```

`auth_user` is never touched.

## Related code files

**Create**
- `apis/migrations/0075_drop_oauth2_provider_tables.py`

**Modify**
- `djangopj/settings.py` — remove `'oauth2_provider',` (L58); rewrite the
  `AUTHENTICATION_BACKENDS` comment (L212-214) that describes the password grant
- `requirements.txt` — remove `django-oauth-toolkit==2.2.0`, `oauthlib==3.2.2`,
  `jwcrypto==1.4.2`, `Deprecated==1.2.13`, `wrapt==1.15.0`

**Delete** — none (the module went in phase 02).

## Implementation steps

1. **Pre-flight on production, BEFORE `migrate`** — this list is unrecoverable afterwards:

```sql
SHOW TABLES LIKE 'oauth2_provider%';        -- confirm exactly the five below
SELECT COUNT(*) FROM oauth2_provider_accesstoken;   -- sessions about to die (already dead
SELECT COUNT(*) FROM oauth2_provider_refreshtoken;  --  in practice: the code stopped reading
SELECT id, name, client_type FROM oauth2_provider_application;  -- them at the phase-02 deploy)
```
   Save the output with the release notes. `mysqldump` before `migrate` is **mandatory**.

2. `djangopj/settings.py`: delete `'oauth2_provider',` from `INSTALLED_APPS`.

3. `djangopj/settings.py`: replace the pre-`AUTHENTICATION_BACKENDS` comment with a JWT one,
   e.g. *"Username/password is the only login flow: `POST /api/auth/login`
   (`apis/views/auth_login.py`) calls `authenticate()` against this backend and mints a JWT."*

4. `requirements.txt`: remove the five pins listed above. Leave `PyJWT==2.6.0` (now a direct
   dependency, not a transitive one — worth a trailing comment saying so, since it used to
   arrive via DOT).

5. Create `apis/migrations/0075_drop_oauth2_provider_tables.py`:

```python
"""Drop the five `oauth2_provider_*` tables left behind by removing django-oauth-toolkit.

Lives in `apis` because the replacement (`apis.RefreshToken`, migration 0074) does --
schema history for auth now belongs to one app. The SQL is cross-app on purpose:
`oauth2_provider` is no longer in INSTALLED_APPS, so it has no migration graph to hang
this on.

`IF EXISTS` is load-bearing: the test database never creates these tables, so a bare
DROP would fail every ./scripts/run-tests.sh run.

Order is child-to-parent. Note `accesstoken` drops BEFORE `idtoken`: DOT 2.x gives
AccessToken a OneToOne to IDToken, so the alphabetical order would violate the FK.

IRREVERSIBLE. Reverse is a no-op -- empty tables would not bring back the tokens, and
they are worthless anyway (the code that could mint or verify them is gone). Recovery =
restore from backup, so `mysqldump` BEFORE `migrate` is mandatory.
"""
from django.db import migrations

DROP_SQL = """
DROP TABLE IF EXISTS oauth2_provider_refreshtoken;
DROP TABLE IF EXISTS oauth2_provider_accesstoken;
DROP TABLE IF EXISTS oauth2_provider_idtoken;
DROP TABLE IF EXISTS oauth2_provider_grant;
DROP TABLE IF EXISTS oauth2_provider_application;
DELETE FROM django_migrations WHERE app = 'oauth2_provider';
"""


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0074_refresh_token'),
    ]

    operations = [
        # A LIST, not one string: MySQLdb's execute() refuses multiple statements.
        migrations.RunSQL(
            sql=[(stmt.strip() + ';') for stmt in DROP_SQL.strip().split(';') if stmt.strip()],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
```

6. Rebuild and verify the dependency tree:
   `docker build -f Dockerfile.test -t calendar-api-test:latest .` then
   `docker run --rm calendar-api-test:latest pip check` → no broken requirements, and
   `pip show django-oauth-toolkit` → not found.

7. `manage.py migrate` against a dev copy that HAS the tables →
   `SHOW TABLES LIKE 'oauth2_provider%';` empty and
   `SELECT COUNT(*) FROM django_migrations WHERE app='oauth2_provider';` → 0.

8. `manage.py migrate` twice in a row → idempotent, no error.

## Todo list

- [x] Pre-flight queries run on production, output saved with the release notes
- [x] `mysqldump` taken
- [x] `'oauth2_provider'` out of `INSTALLED_APPS`
- [x] `AUTHENTICATION_BACKENDS` comment rewritten
- [x] Five pins removed from `requirements.txt`; `PyJWT` annotated as direct
- [x] `apis/migrations/0075_drop_oauth2_provider_tables.py` created
- [x] `pip check` clean in the rebuilt test image
- [x] `migrate` on a dev DB with the tables → both verification queries pass
- [x] `migrate` run twice → idempotent

## Deviations from plan

1. **Circular FK in DOT 2.2.0 discovered during code review**: The plan's drop order was incomplete. Migration 0075 now wraps all DROP statements in `SET FOREIGN_KEY_CHECKS=0/1` to disable constraint checking during the drops. This handles the circular FK (`refreshtoken.access_token → accesstoken` and `accesstoken.source_refresh_token → refreshtoken`) that would otherwise cause MySQL 5.7 to reject the drops with ERROR 1217.
2. **Post-deploy ops task remains OPEN**: The risk table item "rehearse migrate against a restored prod dump" cannot be done from this machine — requires ops to execute before release.

## Success criteria

- [x] `grep -rni "oauth2_provider\|oauthlib\|django-oauth-toolkit" --include=*.py --include=*.txt .`
  matches only the new migration's docstring/SQL, the tests (phase 04) and docs (phase 05).
- [x] `SHOW TABLES LIKE 'oauth2_provider%';` → 0 rows on a migrated database.
- [x] A fresh test database builds and the migration is a silent no-op.

## Risk assessment

| Risk | L×I | Mitigation |
|---|---|---|
| Bare `DROP` breaks every test run | Med×High | `IF EXISTS` on all five + the fresh-DB run in phase 04 |
| FK violation from the wrong drop order | Med×Med | Child-first order, `accesstoken` before `idtoken`; dev-DB run in step 7 |
| Multi-statement string rejected by MySQLdb | Med×Med | Statements passed as a list |
| Removing a pin that something else needs | Low×High | `pip check` in step 6; `google-auth`, `python-jose`, `cryptography`, `rsa`, `pyasn1`, `ecdsa` explicitly kept |
| DOT 2.2.0 has a sixth table this list misses | Low×Med | Step 1's `SHOW TABLES LIKE` is the authority — reconcile before writing the file |
| Irreversible drop ships with the code that stopped needing it; a same-day rollback loses the rows | Med×Low | Rows are already worthless post-phase-02 (no code can verify those tokens). If ops still wants a soak, ship 0075 in the next release — the file is self-contained |
| `migrate` runs before the new image is deployed | Low×Med | Deploy order: image first, `migrate` second |

## Security considerations

- Net positive: the dropped tables stored bearer access/refresh tokens and a hashed client
  secret. Removing them shrinks the blast radius of a future DB dump.
- Removing `oauthlib`/`jwcrypto`/`Deprecated` removes three unmaintained-in-this-project
  attack-surface packages from the image.
- The pre-flight output contains no PII beyond row counts and an application name — but keep
  it out of the repo anyway.

## Next steps

Phase 04 makes the suite green again.
