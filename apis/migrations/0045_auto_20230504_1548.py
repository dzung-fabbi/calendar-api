# Generated by Django 3.1 on 2023-05-04 08:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0044_bookcalendar'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookcalendar',
            name='phone',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='bookcalendar',
            name='email',
            field=models.EmailField(blank=True, max_length=255, null=True),
        ),
    ]