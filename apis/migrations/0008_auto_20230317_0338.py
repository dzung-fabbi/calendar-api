# Generated by Django 3.1 on 2023-03-17 03:38

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0007_auto_20230317_0326'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='khaisonhung',
            name='am_phu_thai_tue',
        ),
        migrations.RemoveField(
            model_name='khaisonhung',
            name='cuu_thoai',
        ),
        migrations.RemoveField(
            model_name='khaisonhung',
            name='luc_hai',
        ),
        migrations.RemoveField(
            model_name='khaisonhung',
            name='tu_phu',
        ),
    ]
