# Generated by Django 3.1 on 2023-04-14 10:02

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0031_auto_20230414_1648'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='saohiepky',
            name='hiepky',
        ),
        migrations.RemoveField(
            model_name='saohiepky',
            name='sao',
        ),
        migrations.DeleteModel(
            name='HiepKy',
        ),
        migrations.DeleteModel(
            name='SaoHiepKy',
        ),
    ]