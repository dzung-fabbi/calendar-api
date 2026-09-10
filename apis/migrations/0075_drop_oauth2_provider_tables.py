"""Drop the five `oauth2_provider_*` tables left behind by removing django-oauth-toolkit.

Lives in `apis` because the replacement (`apis.RefreshToken`, migration 0074) does --
schema history for auth now belongs to one app. The SQL is cross-app on purpose:
`oauth2_provider` is no longer in INSTALLED_APPS, so it has no migration graph to
hang this on. Same shape as `giapha/migrations/0007_drop_social_auth_tables.py`.

`IF EXISTS` is load-bearing, not defensive style: the test database never creates
these tables, so a bare DROP would fail every `./scripts/run-tests.sh` run.

FOREIGN_KEY_CHECKS IS SWITCHED OFF FOR THE DROPS, AND THAT IS LOAD-BEARING: DOT
2.2.0 has a CIRCULAR FK -- `refreshtoken.access_token_id -> accesstoken` AND
`accesstoken.source_refresh_token_id -> refreshtoken` (added by its migration
`0002_auto_20190406_1805`). No drop order satisfies a cycle; MySQL 5.7 rejects
the first DROP with error 1217/3730. The test database never notices (the tables
do not exist there), which is exactly why this was missed once. `SET
FOREIGN_KEY_CHECKS` is session-scoped and every statement in the list runs on
the same connection, so the pair below brackets the drops and nothing else.
The order inside is still child-to-parent for readability. `auth_user` is never
touched.

The final DELETE removes the app's own bookkeeping rows so `showmigrations` stops
listing an app that no longer exists.

IRREVERSIBLE. Reverse is a no-op: empty tables would not bring back the tokens,
and they are worthless anyway -- the code that could mint or verify them is
gone. Recovery = restore from backup, so `mysqldump` BEFORE `migrate` is
mandatory (docs/deployment-guide.md).
"""
from django.db import migrations

DROP_SQL = """
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS oauth2_provider_refreshtoken;
DROP TABLE IF EXISTS oauth2_provider_accesstoken;
DROP TABLE IF EXISTS oauth2_provider_idtoken;
DROP TABLE IF EXISTS oauth2_provider_grant;
DROP TABLE IF EXISTS oauth2_provider_application;
SET FOREIGN_KEY_CHECKS = 1;
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
