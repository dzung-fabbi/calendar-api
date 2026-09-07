"""The caller's own profile: read shape and the PATCH input.

`UserProfile.is_free` / `.expiry_datetime` are billing internals and appear in
NEITHER serializer below -- explicit whitelists, per
`docs/code-standards.md` -> Serializers.
"""

import datetime as dt
from urllib.parse import urlsplit

from rest_framework import serializers

from apis.models import UserProfile
from apis.serializers.auth import reject_non_bmp

# Vietnamese mobile numbers: a leading 0 or +84, then 9 digits.
PHONE_MAX_DIGITS = 15
INVALID_PHONE = 'Số điện thoại không hợp lệ.'
INVALID_AVATAR_SCHEME = 'Ảnh đại diện phải là đường dẫn http hoặc https.'
BIRTH_DATE_IN_FUTURE = 'Ngày sinh không được ở tương lai.'

ALLOWED_AVATAR_SCHEMES = ('http', 'https')


class UserProfileSerializer(serializers.ModelSerializer):
    """Read shape. Every field has a non-null default so that a user with no
    profile row (accounts predating migration 0055) still serialises."""

    class Meta:
        model = UserProfile
        fields = ['phone', 'birth_date', 'avatar_url']
        read_only_fields = fields


class ProfileUpdateSerializer(serializers.Serializer):
    """PATCH body for `/api/me`. Every field optional -- this is a partial
    update, and an absent key must not blank a stored value."""

    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    birth_date = serializers.DateField(required=False, allow_null=True)
    avatar_url = serializers.URLField(required=False, allow_blank=True, max_length=500)

    def validate_first_name(self, value):
        return reject_non_bmp(value)

    def validate_last_name(self, value):
        return reject_non_bmp(value)

    def validate_phone(self, value):
        if not value:
            return value
        compact = value.replace(' ', '').replace('-', '').replace('.', '')
        digits = compact[1:] if compact.startswith('+') else compact
        if not digits.isdigit() or not 8 <= len(digits) <= PHONE_MAX_DIGITS:
            raise serializers.ValidationError(INVALID_PHONE)
        return compact

    def validate_birth_date(self, value):
        # A future birth date is always a client bug or a typo, and it would
        # quietly poison anything that later computes an age from it.
        if value is not None and value > dt.date.today():
            raise serializers.ValidationError(BIRTH_DATE_IN_FUTURE)
        return value

    def validate_avatar_url(self, value):
        """Reject any scheme but http/https.

        DRF's `URLField` accepts `javascript:` and `data:` URLs. This value is
        stored and then handed to every client that renders the profile, so an
        unchecked scheme here is a stored-XSS primitive delivered through the
        API -- the one field on this endpoint whose content is later executed
        rather than displayed.
        """
        if not value:
            return value
        if urlsplit(value).scheme.lower() not in ALLOWED_AVATAR_SCHEMES:
            raise serializers.ValidationError(INVALID_AVATAR_SCHEME)
        return value

    def create(self, validated_data):
        raise NotImplementedError

    def update(self, instance, validated_data):
        raise NotImplementedError
