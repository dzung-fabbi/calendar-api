# Generated by Django 3.1.14 on 2023-07-07 10:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0066_auto_20230707_1645'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sao',
            name='level',
            field=models.FloatField(blank=True, null=True, verbose_name='Cấp độ'),
        ),
        migrations.AlterField(
            model_name='thansatbyyearsao',
            name='cung_son',
            field=models.IntegerField(blank=True, choices=[(1, 'Cung'), (2, 'Son')], editable=False, null=True),
        ),
    ]
