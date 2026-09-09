"""Drop the five `social_django` tables left behind by removing Facebook/Google login.

Lives in `giapha` rather than `apis` because `giapha` is the app under active
development -- a reviewer looking for recent schema history looks here, and `apis`'
73 migrations are effectively frozen. The SQL is cross-app on purpose: `social_django`
is no longer in INSTALLED_APPS, so it has no migration graph of its own to hang this on.

`IF EXISTS` is load-bearing, not defensive style: the test database never creates these
tables (the app is gone from INSTALLED_APPS), so a bare DROP would fail every single
`./scripts/run-tests.sh` run.

IRREVERSIBLE. Reverse is a no-op -- recreating empty tables would not bring back the
provider identities. Recovery = restore from backup, so `mysqldump` BEFORE `migrate`
is mandatory, not advisory (see `docs/deployment-guide.md`).
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
        # Statements go in as a LIST: MySQLdb's `execute()` refuses more than one
        # statement in a single string. `social_auth_usersocialauth` is first
        # because it is the only one holding an FK (`user_id -> auth_user`) --
        # the child drops before anything else.
        migrations.RunSQL(
            sql=[(stmt.strip() + ';') for stmt in DROP_SQL.strip().split(';') if stmt.strip()],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
