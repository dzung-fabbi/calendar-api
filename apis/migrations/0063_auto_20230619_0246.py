# Generated by Django 3.1 on 2023-06-19 02:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0062_bankconfig_qr_img'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appointmentdate',
            name='before_days',
            field=models.DurationField(default=0),
        ),
    ]
