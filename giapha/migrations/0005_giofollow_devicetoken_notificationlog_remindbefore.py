"""Push-notification tables plus the clan-level reminder lead time.

Three new tables (`GioFollow`, `DeviceToken`, `GioNotificationLog`) and one
column on `Clan`. Nothing outside this migration depends on them yet, so it
drops cleanly on its own -- revert this before 0004.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('giapha', '0004_clanmember_person_binding'),
    ]

    operations = [
        migrations.AddField(
            model_name='clan',
            name='gio_remind_before_days',
            field=models.IntegerField(default=3, verbose_name='Nhắc giỗ trước (ngày)'),
        ),
        migrations.CreateModel(
            name='DeviceToken',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=255, unique=True, verbose_name='Token thiết bị')),
                ('platform', models.CharField(choices=[('ios', 'iOS'), ('android', 'Android'), ('web', 'Web')], max_length=16, verbose_name='Nền tảng')),
                ('is_active', models.BooleanField(default=True, verbose_name='Còn hiệu lực')),
                ('last_seen', models.DateTimeField(auto_now=True, verbose_name='Lần cuối hoạt động')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='device_tokens', to=settings.AUTH_USER_MODEL, verbose_name='Người dùng')),
            ],
            options={
                'verbose_name': 'Thiết bị nhận thông báo',
                'verbose_name_plural': 'Thiết bị nhận thông báo',
            },
        ),
        migrations.CreateModel(
            name='GioNotificationLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('solar_date', models.DateField(db_index=True, verbose_name='Ngày giỗ dương lịch')),
                ('sent_at', models.DateTimeField(auto_now_add=True, verbose_name='Thời điểm gửi')),
                ('status', models.CharField(choices=[('sent', 'Đã gửi'), ('failed', 'Thất bại')], max_length=16, verbose_name='Trạng thái')),
                ('error', models.CharField(blank=True, max_length=255, verbose_name='Lỗi')),
                ('person', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gio_notifications', to='giapha.person', verbose_name='Người được nhắc giỗ')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gio_notifications', to=settings.AUTH_USER_MODEL, verbose_name='Người nhận thông báo')),
            ],
            options={
                'verbose_name': 'Nhật ký nhắc giỗ',
                'verbose_name_plural': 'Nhật ký nhắc giỗ',
                'unique_together': {('person', 'user', 'solar_date')},
            },
        ),
        migrations.CreateModel(
            name='GioFollow',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(verbose_name='Bật theo dõi')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Ngày cập nhật')),
                ('person', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gio_follows', to='giapha.person', verbose_name='Người được theo dõi')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gio_follows', to=settings.AUTH_USER_MODEL, verbose_name='Người theo dõi')),
            ],
            options={
                'verbose_name': 'Theo dõi giỗ',
                'verbose_name_plural': 'Theo dõi giỗ',
                'unique_together': {('person', 'user')},
            },
        ),
    ]
