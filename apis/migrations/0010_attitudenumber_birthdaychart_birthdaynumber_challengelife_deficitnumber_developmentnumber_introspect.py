# Generated by Django 3.1 on 2023-03-27 08:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0009_auto_20230317_0835'),
    ]

    operations = [
        migrations.CreateModel(
            name='AttitudeNumber',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField(blank=True, null=True)),
                ('number_page', models.IntegerField()),
            ],
            options={
                'db_table': 'attitude_number',
            },
        ),
        migrations.CreateModel(
            name='BirthdayChart',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField(blank=True, null=True)),
                ('number_page', models.IntegerField()),
            ],
            options={
                'db_table': 'birthday_chart',
            },
        ),
        migrations.CreateModel(
            name='BirthdayNumber',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField(blank=True, null=True)),
                ('number_page', models.IntegerField()),
            ],
            options={
                'db_table': 'birthday_number',
            },
        ),
        migrations.CreateModel(
            name='ChallengeLife',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField(blank=True, null=True)),
                ('number_page', models.IntegerField()),
            ],
            options={
                'db_table': 'challenge_life',
            },
        ),
        migrations.CreateModel(
            name='DeficitNumber',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField(blank=True, null=True)),
                ('number_page', models.IntegerField()),
            ],
            options={
                'db_table': 'deficit_number',
            },
        ),
        migrations.CreateModel(
            name='DevelopmentNumber',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField(blank=True, null=True)),
                ('number_page', models.IntegerField()),
            ],
            options={
                'db_table': 'development_number',
            },
        ),
        migrations.CreateModel(
            name='IntrospectiveNumber',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField(blank=True, null=True)),
                ('number_page', models.IntegerField()),
            ],
            options={
                'db_table': 'introspective_number',
            },
        ),
        migrations.CreateModel(
            name='KarmicNumber',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField(blank=True, null=True)),
                ('number_page', models.IntegerField()),
            ],
            options={
                'db_table': 'karmic_number',
            },
        ),
        migrations.CreateModel(
            name='LifePeak',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField(blank=True, null=True)),
                ('number_page', models.IntegerField()),
            ],
            options={
                'db_table': 'life_peak',
            },
        ),
        migrations.CreateModel(
            name='MainNumber',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.IntegerField()),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField(blank=True, null=True)),
                ('number_page', models.IntegerField()),
            ],
            options={
                'db_table': 'main_number',
            },
        ),
        migrations.CreateModel(
            name='MatureNumber',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField(blank=True, null=True)),
                ('number_page', models.IntegerField()),
            ],
            options={
                'db_table': 'mature_number',
            },
        ),
        migrations.CreateModel(
            name='MissionNumber',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField(blank=True, null=True)),
                ('number_page', models.IntegerField()),
            ],
            options={
                'db_table': 'mission_number',
            },
        ),
        migrations.CreateModel(
            name='PersonalMonthNumber',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField(blank=True, null=True)),
                ('number_page', models.IntegerField()),
            ],
            options={
                'db_table': 'personal month_number',
            },
        ),
        migrations.CreateModel(
            name='PhoneNumber',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField(blank=True, null=True)),
                ('number_page', models.IntegerField()),
            ],
            options={
                'db_table': 'phone_number',
            },
        ),
        migrations.CreateModel(
            name='SoulsNumber',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField(blank=True, null=True)),
                ('number_page', models.IntegerField()),
            ],
            options={
                'db_table': 'souls_number',
            },
        ),
        migrations.CreateModel(
            name='StagesOfLife',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField(blank=True, null=True)),
                ('number_page', models.IntegerField()),
            ],
            options={
                'db_table': 'stages_of_life',
            },
        ),
    ]