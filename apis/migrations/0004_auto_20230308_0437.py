# Generated by Django 3.1 on 2023-03-08 04:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0003_quynhan'),
    ]

    operations = [
        migrations.CreateModel(
            name='TuDaiCatThoi',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hour', models.CharField(max_length=255)),
                ('can_ngay_1', models.CharField(max_length=255, null=True)),
                ('can_ngay_2', models.CharField(max_length=255, null=True)),
                ('can_ngay_3', models.CharField(max_length=255, null=True)),
                ('can_ngay_4', models.CharField(max_length=255, null=True)),
                ('can_ngay_5', models.CharField(max_length=255, null=True)),
                ('can_ngay_6', models.CharField(max_length=255, null=True)),
                ('can_ngay_7', models.CharField(max_length=255, null=True)),
                ('can_ngay_8', models.CharField(max_length=255, null=True)),
                ('can_ngay_9', models.CharField(max_length=255, null=True)),
                ('can_ngay_10', models.CharField(max_length=255, null=True)),
                ('tiet_khi', models.CharField(max_length=255)),
            ],
            options={
                'db_table': 'tu_dai_cat_thoi',
            },
        ),
        migrations.AlterField(
            model_name='quynhan',
            name='am_duong',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='quynhan',
            name='quy_nhan',
            field=models.CharField(max_length=255, null=True),
        ),
    ]
