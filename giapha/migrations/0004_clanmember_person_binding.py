"""Bind a ClanMember to a node in the tree (`ClanMember.person`).

Purely additive: one nullable column plus its unique index. No backfill --
there is no data anywhere from which to guess which Person a given user is,
and a wrong guess would send that user another family's reminders. Every
existing row starts at NULL and the user picks themselves via
`PUT /clans/{id}/toi-la`.

Reversible with a plain `RemoveField`. Reverting on a live database DOES lose
every binding entered so far; dump `giapha_clanmember.person_id` first.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('giapha', '0003_claninvite_role_no_owner'),
    ]

    operations = [
        migrations.AddField(
            model_name='clanmember',
            name='person',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='member_link', to='giapha.person', verbose_name='Là ai trong cây'),
        ),
    ]
