# Generated for phase 9 (chia sẻ công khai): 'public' (unused elsewhere) is
# replaced by 'public_link' in `Clan.visibility`'s choices. Choices are not a
# DB-level constraint under MySQL -- this AlterField changes only Django's
# migration state / admin form, not the column type or any stored data.
#
# NO RunPython NEEDED even if a pre-phase-9 row somehow has the literal
# string 'public' stored in this column: that value appears nowhere but the
# old choices tuple in this very file's history (never written by any view
# or admin action), and every gate that decides "is this clan's link live"
# (`selectors.clan.get_clan_by_public_slug`, `views.clan.
# ClanPublicLinkAPIView`) is an ALLOWLIST equality check against the string
# 'public_link' specifically -- a stray 'public' row simply fails every one
# of those checks and behaves as private, i.e. fails closed on its own.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('giapha', '0005_giofollow_devicetoken_notificationlog_remindbefore'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clan',
            name='visibility',
            field=models.CharField(
                choices=[('private', 'Riêng tư'), ('public_link', 'Công khai qua link')],
                default='private', max_length=16, verbose_name='Chế độ hiển thị',
            ),
        ),
    ]
