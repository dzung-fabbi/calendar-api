"""Request-body serializers for the presigned-upload endpoints (`views/photo.py`).

Response shapes for `photo-upload-url` and `photo-urls` are plain ad-hoc
dicts built in the view -- there is no model backing `upload_url`/`key`/
`expires_in`, and `has_photo`/`photo_url` already live on `serializers.tree`
and `serializers.person`. This module only validates what a client sends in.
"""

from rest_framework import serializers

# `content_type` allowlist -- phase-08 spec. Kept here (not in `services.storage`)
# so the service layer stays free of HTTP-shaped validation concerns.
ALLOWED_CONTENT_TYPES = ('image/jpeg', 'image/png', 'image/webp')
MAX_PHOTO_BYTES = 5 * 1024 * 1024
PHOTO_URLS_MAX_IDS = 100


class PhotoUploadUrlRequestSerializer(serializers.Serializer):
    """`POST .../photo-upload-url` body. `size` is only a client-declared
    hint used to reject an obviously-oversized request early -- it is NOT
    what enforces the 5MB cap (see `services.storage.presign_put`'s
    docstring); the real enforcement is the confirm step's `head()` check.
    """

    content_type = serializers.ChoiceField(choices=ALLOWED_CONTENT_TYPES)
    size = serializers.IntegerField(min_value=1, max_value=MAX_PHOTO_BYTES)


class PhotoConfirmSerializer(serializers.Serializer):
    """`POST .../photo` body -- just the key the client already PUT to."""

    key = serializers.CharField(max_length=512)


class PhotoUrlsRequestSerializer(serializers.Serializer):
    """`POST /photo-urls` body. Capped at `PHOTO_URLS_MAX_IDS` -- this
    endpoint exists specifically so `/tree` never has to mint one presigned
    URL per node (phase-08 spec); an uncapped batch would just move that
    same cost here.
    """

    person_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, max_length=PHOTO_URLS_MAX_IDS,
    )
