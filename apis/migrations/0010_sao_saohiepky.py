# Generated by Django 3.1 on 2023-03-23 15:04

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0009_auto_20230317_0835'),
    ]

    operations = [
        migrations.CreateModel(
            name='Sao',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('property', models.CharField(max_length=255)),
                ('good_ugly_stars', models.IntegerField(blank=True, null=True)),
                ('is_mountain', models.TextField(blank=True, null=True)),
            ],
            options={
                'db_table': 'sao',
            },
        ),
        migrations.CreateModel(
            name='SaoHiepKy',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hiepky', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apis.hiepky')),
                ('sao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apis.sao')),
            ],
        ),
    ]
