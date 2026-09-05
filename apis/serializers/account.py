"""Serializers for the authenticated user."""

from django.contrib.auth.models import User
from rest_framework import serializers


class UserSerializer(serializers.ModelSerializer):
    """The caller's own profile.

    Explicitly whitelisted. This used to be `fields = '__all__'`, which on the
    auth User model ships the password hash, `is_superuser`/`is_staff`, and the
    raw permission and group ids to anyone who can authenticate.
    """

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'date_joined',
            'last_login',
        ]
        read_only_fields = fields
