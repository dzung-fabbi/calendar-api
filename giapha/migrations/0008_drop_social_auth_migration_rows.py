"""Delete the `django_migrations` rows left by `social_django`'s legacy app labels.

`0007_drop_social_auth_tables` dropped the five tables and cleaned the rows
recorded under `app='social_django'`. It missed nine more: the same package
also registered under two OLDER app labels, and those rows survived.

* `social_auth` (5 rows) -- the label `social_django` used before it was renamed.
* `default` (4 rows) -- older still, from `social.apps.django_app.default`.

Both sets carry that package's own migration filenames (`0001_initial`,
`0002_add_related_name`, `0003_alter_email_max_length`, `0004_auto_20160423_0400`,
`0005_auto_20160727_2333`) and on this database were all applied in the same
`migrate` run.

Harmless in themselves -- nothing reads them once the app is gone from
INSTALLED_APPS -- but they make `showmigrations` and any audit of what this
database has applied lie about apps that no longer exist.

MATCHED BY (app, name) PAIRS, NOT BY APP ALONE. `default` is a plausible label
for some future app, and `DELETE ... WHERE app = 'default'` would then be a
loaded gun aimed at it. Naming the exact filenames keeps this migration's blast
radius fixed at the nine rows it was written for, forever.

Reverse is a no-op: re-inserting bookkeeping rows for absent apps would be
worse than the state this fixes, not a restoration of anything.
"""
from django.db import migrations

LEGACY_APPS = ('social_auth', 'default')
LEGACY_NAMES = (
    '0001_initial',
    '0002_add_related_name',
    '0003_alter_email_max_length',
    '0004_auto_20160423_0400',
    '0005_auto_20160727_2333',
)


def delete_legacy_rows(apps, schema_editor):
    placeholders_apps = ', '.join(['%s'] * len(LEGACY_APPS))
    placeholders_names = ', '.join(['%s'] * len(LEGACY_NAMES))
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'DELETE FROM django_migrations WHERE app IN ({}) AND name IN ({})'.format(
                placeholders_apps, placeholders_names,
            ),
            list(LEGACY_APPS) + list(LEGACY_NAMES),
        )


class Migration(migrations.Migration):

    dependencies = [
        ('giapha', '0007_drop_social_auth_tables'),
    ]

    operations = [
        # RunPython, not RunSQL: the `IN (...)` lists are built from the tuples
        # above so the SQL cannot drift out of sync with the documented row set.
        migrations.RunPython(delete_legacy_rows, migrations.RunPython.noop),
    ]
