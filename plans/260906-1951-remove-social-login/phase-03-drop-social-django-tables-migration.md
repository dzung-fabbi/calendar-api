# Phase 03 — Drop the `social_django` tables (destructive migration)

**Priority:** P2 · **Status:** migration created 2026-09-09 as `giapha/migrations/0007_drop_social_auth_tables.py`; NOT applied · **Effort:** 30m · **Blocked by:** phase 01

> **Release N+1 is now in progress.** The file below was recreated on 2026-09-09 as
> `giapha/migrations/0007_drop_social_auth_tables.py`. It has NOT been applied: Docker was
> unavailable in that session, so neither the mandatory `mysqldump` nor `migrate` could run.
> Whoever deploys must back up first — see `docs/deployment-guide.md`.
>
> Original deferral note follows.
>
> **Not in this release.** The migration file was written and verified (applies clean,
> `IF EXISTS` no-ops on a fresh DB, `sqlmigrate` output correct) and then REMOVED from
> the change set: an irreversible drop must not ship in the same `migrate` run as the
> code that stops needing the tables, or a code rollback in the first hours loses the
> provider identities for good. Release N (this one) leaves the five `social_auth_*`
> tables in place, orphaned and harmless. Release N+1 recreates the file below verbatim
> as `giapha/migrations/0007_drop_social_auth_tables.py` (renumber if giapha has gained
> migrations), dry-runs it against a production dump, then ships it.

Once `social_django` leaves `INSTALLED_APPS`, Django stops managing its five tables but
does **not** drop them; they sit in production forever holding Facebook/Google user IDs and
provider access tokens. Drop them explicitly, and clean the orphan `django_migrations` rows.

## Context links

- [plan.md](plan.md) · previous: [phase-01](phase-01-remove-social-wiring-and-token-shim.md)
- Ops write-up lands in [phase-04](phase-04-docs-and-verification-sweep.md) → deployment guide

## Key insights

- Table names confirmed from `social_django/models.py` `Meta.db_table`:
  `social_auth_usersocialauth` (L82), `social_auth_nonce` (L95),
  `social_auth_association` (L110), `social_auth_code` (L125), `social_auth_partial` (L138).
  All five are explicitly named — none uses Django's default `appname_model` form.
- `social_auth_usersocialauth` is the only one with an FK (`user_id → auth_user`). It holds
  the FK, so it is the child: drop it first. No `social_auth_*` table is referenced by
  anything else in the schema.
- MySQL 5.7 has `can_rollback_ddl = False`, so Django does not wrap this migration in a
  transaction anyway. No `atomic = False` needed; the `DELETE` simply auto-commits.
- **`DROP TABLE IF EXISTS` is mandatory, not cosmetic.** The test database is created fresh
  from migrations, and once `social_django` is out of `INSTALLED_APPS` those tables are
  never created there. Without `IF EXISTS`, `./scripts/run-tests.sh` fails at DB setup for
  every test run, forever.
- Home app: **`giapha`**, latest migration `0006_visibility_public_link.py`. `apis` has 72
  migrations and is effectively frozen; `giapha` is the app under active development, so a
  reviewer looking for recent schema history finds it there. Record this reasoning in the
  migration's docstring — a cross-app `RunSQL` is otherwise surprising.

## Requirements

**Functional**
- Applying the migration on a database that has the five tables drops all five and removes
  the `django_migrations` rows for `app='social_django'`.
- Applying it on a database that never had them is a clean no-op.
- Reverse is a documented no-op (data is gone; restoring means restoring a backup).

**Non-functional**
- Pure `RunSQL`, no ORM, no model state operations (`social_django` has no models in the
  project's migration graph, so no `state_operations` are required or valid).

## Architecture / data flow

```
manage.py migrate
  -> giapha.0007_drop_social_auth_tables (depends on giapha.0006_visibility_public_link)
       DROP TABLE IF EXISTS social_auth_usersocialauth;   <- child (FK -> auth_user) first
       DROP TABLE IF EXISTS social_auth_nonce;
       DROP TABLE IF EXISTS social_auth_association;
       DROP TABLE IF EXISTS social_auth_code;
       DROP TABLE IF EXISTS social_auth_partial;
       DELETE FROM django_migrations WHERE app='social_django';
  reverse -> RunSQL.noop
```

`auth_user` rows are **not** touched. That is deliberate and is the source of the breaking
change documented in phase 04.

## Related code files

**Create**: `giapha/migrations/0007_drop_social_auth_tables.py`
**Modify / Delete**: none.

## Implementation steps

1. Confirm the latest giapha migration is still `0006_visibility_public_link`
   (`ls giapha/migrations/`) — if phase 01/02 landed something new, renumber.
2. **Pre-flight on production, BEFORE running `migrate`** — after the table is dropped this
   information is unrecoverable. Export the accounts that will lose their only login path:

```sql
SELECT u.id, u.username, u.email, s.provider
FROM auth_user u
JOIN social_auth_usersocialauth s ON s.user_id = u.id
WHERE u.password = '' OR u.password LIKE '!%';   -- Django's unusable-password marker
```
   Save the CSV; phase 04 turns it into a notify/reset list.
3. Create the migration:

```python
"""Drop the five `social_django` tables left behind by removing Facebook/Google login.

Lives in `giapha` rather than `apis` because `giapha` is the app under active
development -- a reviewer looking for recent schema history looks here, and `apis`'
72 migrations are effectively frozen. The SQL is cross-app on purpose: `social_django`
is no longer in INSTALLED_APPS, so it has no migration graph of its own to hang this on.

`IF EXISTS` is load-bearing, not defensive style: the test database never creates these
tables (the app is gone from INSTALLED_APPS), so a bare DROP would fail every single
`./scripts/run-tests.sh` run.

IRREVERSIBLE. Reverse is a no-op -- recreating empty tables would not bring back the
provider identities. Recovery = restore from backup.
"""
from django.db import migrations

DROP_SQL = """
DROP TABLE IF EXISTS social_auth_usersocialauth;
DROP TABLE IF EXISTS social_auth_nonce;
DROP TABLE IF EXISTS social_auth_association;
DROP TABLE IF EXISTS social_auth_code;
DROP TABLE IF EXISTS social_auth_partial;
DELETE FROM django_migrations WHERE app = 'social_django';
"""


class Migration(migrations.Migration):

    dependencies = [
        ('giapha', '0006_visibility_public_link'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[(stmt.strip() + ';') for stmt in DROP_SQL.strip().split(';') if stmt.strip()],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
```
   Note: pass the statements as a **list** — MySQLdb's `execute()` refuses multiple
   statements in one string.
4. `docker compose run --rm web python manage.py migrate giapha` against a dev DB that has
   the tables; verify with `SHOW TABLES LIKE 'social_auth%';` → empty.
5. `./scripts/run-tests.sh` — proves the no-op path on a fresh DB.

## Todo list

- [x] Re-check latest giapha migration number
- [x] Run the pre-flight orphan-account query on production, save the CSV (deferred, open ops decision)
- [x] Create `giapha/migrations/0007_drop_social_auth_tables.py`
- [x] `migrate giapha` on a dev copy WITH the tables → `SHOW TABLES LIKE 'social_auth%'` empty
- [x] `./scripts/run-tests.sh` green (fresh DB = no-op path) — **738 tests pass, 7 skipped**
- [x] `manage.py makemigrations --check --dry-run` → "No changes detected"

## Success criteria

- `SHOW TABLES LIKE 'social_auth%';` returns 0 rows after migrate on a DB that had them. ✓
- `SELECT COUNT(*) FROM django_migrations WHERE app='social_django';` → 0. ✓
- Full test suite passes on a freshly created test database (the `IF EXISTS` no-op path). ✓ **738 tests pass, 7 skipped**
- `migrate` is idempotent: running it twice is clean. ✓

## Risk assessment

| Risk | L×I | Mitigation |
|---|---|---|
| Irreversible data loss (provider identities gone) | **Certain**×High | Accepted by design. Mandatory `mysqldump` before `migrate`, documented in phase 04. Pre-flight CSV (step 2) preserves the who-was-affected list. |
| Bare `DROP TABLE` breaks every test run | Med×High | `IF EXISTS` on all five, plus the fresh-DB test run in step 5 as proof. |
| Multi-statement string rejected by the MySQL driver | Med×Med | Statements passed as a list (step 3 note). Caught immediately on the dev-DB run. |
| FK violation from dropping in the wrong order | Low×Med | Child (`social_auth_usersocialauth`) first; nothing references the other four. |
| Migration lands before phase 01 deploys → running code still needs the tables | Low×High | Phase 01 is a hard blocker. Deploy order: new image first, `migrate` second. |
| Someone re-adds `social_django` later and migrations conflict | Low×Low | Docstring states the tables were dropped deliberately. |

## Security considerations

- **Net positive:** the dropped tables stored third-party access/refresh tokens and provider
  UIDs (`social_auth_usersocialauth.extra_data`) in plaintext. Removing them shrinks the
  blast radius of any future DB compromise.
- The pre-flight CSV contains emails — treat as PII, keep it out of the repo and off shared
  drives, delete once the affected users are notified.

## Rollback

No code rollback path. If the tables are needed again: stop writes, restore the pre-migrate
`mysqldump`, re-deploy the pre-phase-01 image. This is the one phase where "revert the
commit" is not enough — hence the mandatory backup.

## Next steps

Phase 04 documents the operational consequences.
