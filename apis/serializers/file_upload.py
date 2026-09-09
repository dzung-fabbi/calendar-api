"""Request-body serializers for the generic file-upload endpoints
(`views/file_upload.py`).

Response shapes are plain ad-hoc dicts built in the view -- there is no model
backing `upload_url`/`key`/`url`, and nothing is persisted. This module only
validates what a client sends in.
"""

from rest_framework import serializers

# `content_type` allowlist. Kept here (not in `services.storage`) so the
# service layer stays free of HTTP-shaped validation concerns.
#
# IMAGES ONLY IS A SECURITY DECISION, not a product limit. These endpoints are
# `AllowAny` (see `views/file_upload.py`), so anyone can put an object in the
# bucket. Be precise about what this buys, though: it constrains the
# `Content-Type` the object is SERVED with, not its bytes -- nothing here
# inspects content, so an arbitrary payload labelled `image/png` can be
# stored. What it prevents is that payload being served as `text/html` or
# `image/svg+xml`, i.e. script execution on the bucket origin. Widening this
# list without adding authentication gives that away.
ALLOWED_CONTENT_TYPES = ('image/jpeg', 'image/png', 'image/webp')
MAX_FILE_BYTES = 5 * 1024 * 1024


class FileUploadUrlRequestSerializer(serializers.Serializer):
    """`POST /api/files/upload-url` body.

    `size` is only a client-declared hint used to reject an obviously-oversized
    request early -- it is NOT what enforces the cap (see
    `services.storage.presign_put`); the real enforcement is the confirm step's
    `head()` check.
    """

    content_type = serializers.ChoiceField(choices=ALLOWED_CONTENT_TYPES)
    size = serializers.IntegerField(min_value=1, max_value=MAX_FILE_BYTES)


class FileConfirmSerializer(serializers.Serializer):
    """`POST /api/files/confirm` body -- just the key the client already PUT to."""

    key = serializers.CharField(max_length=512)
