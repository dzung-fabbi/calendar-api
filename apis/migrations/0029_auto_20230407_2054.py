# Generated by Django 3.1 on 2023-04-07 13:54

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0028_auto_20230407_2051'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='saohour7',
            unique_together={('hour_7', 'sao')},
        ),
    ]
