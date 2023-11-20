# Generated by Django 3.1.14 on 2023-07-19 07:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0070_sao_level'),
    ]

    operations = [
        migrations.CreateModel(
            name='DirectionConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.FloatField(verbose_name='giá trị')),
            ],
            options={
                'verbose_name': 'Cài đặt phương hướng tốt xấu',
                'verbose_name_plural': 'Cài đặt phương hướng tốt xấu',
            },
        ),
    ]