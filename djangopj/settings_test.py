"""Test settings.

Runs against a real MySQL 5.7 service rather than SQLite. This is deliberate:
the application relies on MySQL's case-insensitive `utf8_unicode_ci` collation
(e.g. HomeAPIView matches the same `lunar_day` param against HiepKy.lunar_day,
whose choices are upper-case, and QuyNhan.can_ngay, whose choices are
capitalised). SQLite compares case-sensitively and would report passes/failures
that do not reflect production.

Bring the database up with `docker compose up -d db` and run the suite with
`./scripts/run-tests.sh`.
"""

import os

# Provide the secrets the real settings module now requires, before importing it.
os.environ.setdefault('DJANGO_SECRET_KEY', 'test-only-secret-key')
os.environ.setdefault('DJANGO_DEBUG', 'False')
os.environ.setdefault('DJANGO_ALLOWED_HOSTS', 'testserver,localhost')

from djangopj.settings import *  # noqa: E402,F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'django-db'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'root'),
        'HOST': os.environ.get('DB_HOST', 'db'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'TEST': {
            # Mirror the production server flags set in docker-compose.yml.
            'CHARSET': 'utf8',
            'COLLATION': 'utf8_unicode_ci',
        },
    }
}

DEBUG = False

# The default PBKDF2 hasher dominates runtime when tests create users.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
