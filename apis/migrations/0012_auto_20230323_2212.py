# Generated by Django 3.1 on 2023-03-23 15:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0011_auto_20230323_2205'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sao',
            name='property',
            field=models.TextField(null=True),
        ),
    ]
