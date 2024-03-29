# Generated by Django 3.1.14 on 2023-05-25 03:54

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('apis', '0057_auto_20230521_1454'),
    ]

    operations = [
        migrations.AddField(
            model_name='dateconfig',
            name='factor_1',
            field=models.FloatField(default=1, verbose_name='Hệ số 1'),
        ),
        migrations.AddField(
            model_name='dateconfig',
            name='factor_2',
            field=models.FloatField(default=2, verbose_name='Hệ số 2'),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL),
        ),
    ]
