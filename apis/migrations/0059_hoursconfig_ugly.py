# Generated by Django 3.1 on 2023-05-28 14:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0058_auto_20230525_1054'),
    ]

    operations = [
        migrations.AddField(
            model_name='hoursconfig',
            name='ugly',
            field=models.FloatField(default=2, verbose_name='Giờ xấu'),
        ),
    ]
