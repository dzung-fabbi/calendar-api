"""Serializers for the authenticated user."""

from django.contrib.auth.models import User
from rest_framework import serializers

from apis.serializers.profile import UserProfileSerializer

# Returned in place of a missing `UserProfile` row. Accounts created before
# migration 0055 have none (the creating signal only fires on insert), and a
# bare `obj.profile` on one of those raises `RelatedObjectDoesNotExist` -- a
# 500 on `me` for the very oldest users. Shape-identical to
# `UserProfileSerializer`, so the response contract does not depend on how old
# the account is.
EMPTY_PROFILE = {'phone': '', 'birth_date': None, 'avatar_url': ''}


class UserSerializer(serializers.ModelSerializer):
    """The caller's own profile.

    Explicitly whitelisted. This used to be `fields = '__all__'`, which on the
    auth User model ships the password hash, `is_superuser`/`is_staff`, and the
    raw permission and group ids to anyone who can authenticate.

    `profile` carries only the user-editable fields; `UserProfile.is_free` and
    `.expiry_datetime` are billing internals and stay out (see
    `apis/serializers/profile.py`).
    """

    profile = serializers.SerializerMethodField()

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
            'profile',
        ]
        read_only_fields = fields

    def get_profile(self, obj):
        # `hasattr` rather than a try/except around `obj.profile`: the same
        # guard `apis/admin/site_config.py.make_done` uses, for the same reason.
        if not hasattr(obj, 'profile'):
            return dict(EMPTY_PROFILE)
        return UserProfileSerializer(obj.profile).data
