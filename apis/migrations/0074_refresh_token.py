"""Create `apis_refreshtoken` -- the stored half of the JWT login flow.

Access tokens are stateless JWTs and have no table. A refresh token row's
ABSENCE is what "revoked" means: rotation, logout and password change all
DELETE, there is no `revoked_at` (see `apis/models/refresh_token.py`).

Reversible; the companion `0075_drop_oauth2_provider_tables` is not.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('apis', '0073_account_profile_and_password_reset'),
    ]

    operations = [
        migrations.CreateModel(
            name='RefreshToken',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token_hash', models.CharField(max_length=64, unique=True, verbose_name='Token băm')),
                ('password_fingerprint', models.CharField(max_length=16, verbose_name='Dấu vết mật khẩu')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(db_index=True, verbose_name='Hết hạn lúc')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='refresh_tokens', to=settings.AUTH_USER_MODEL, verbose_name='Người dùng')),
            ],
            options={
                'verbose_name': 'Refresh token',
                'verbose_name_plural': 'Refresh token',
            },
        ),
    ]
