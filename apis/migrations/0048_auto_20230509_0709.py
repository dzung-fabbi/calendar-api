# Generated by Django 3.1 on 2023-05-09 07:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0047_appointmentdate'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appointmentdate',
            name='date',
            field=models.DateField(null=True),
        ),
    ]
