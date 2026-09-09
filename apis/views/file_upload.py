"""Presigned S3/R2 upload endpoints for generic files.

Django never receives file bytes. The client asks `files/upload-url` for a
presigned `PUT`, uploads directly to S3/R2, then calls `files/confirm` to get a
presigned `GET` back -- the confirm step is what verifies, server-side, that the
object actually exists, is under the size cap, and has an allowed content type.
Never on the client's say-so. See `apis/services/storage.py` for why a presigned
`PUT` cannot enforce the size cap up front.

NOTHING IS PERSISTED. No model, no row, no query -- the client owns the `key`
and calls confirm again for a fresh URL when the old one expires.

UNAUTHENTICATED ON PURPOSE (a deliberate, accepted risk): both views are
`AllowAny` with only a throttle in front, so anyone can put an object in the
bucket. That throttle is NOT a real barrier -- see the note in
`djangopj/settings.py` -> `REST_FRAMEWORK`: per-IP bucketing is only meaningful
once `DJANGO_NUM_PROXIES` matches the real proxy count, and enough source IPs
get around it regardless.

The images-only allowlist narrows the damage but does NOT bound what can be
stored: `head()` verifies the `Content-Type` LABEL, and no code here inspects a
single byte of the object (a presigned design cannot). A caller can store an
arbitrary 5MB payload labelled `image/png`. What the allowlist actually buys is
control over what the object is SERVED AS -- a correct `image/png` header stops
a browser rendering a stored HTML payload as a page. Adding a content type here
without adding authentication widens that, and `text/html` or `image/svg+xml`
would hand out script execution on the bucket's origin.

STORAGE UNCONFIGURED -> 503 ON BOTH VIEWS, and nowhere else. The rest of the
API must keep working on a host with no S3/R2 credentials set at all.
"""

import re
import uuid

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apis.exceptions import BadRequestException, ServiceUnavailableException
from apis.serializers.file_upload import (
    ALLOWED_CONTENT_TYPES,
    MAX_FILE_BYTES,
    FileConfirmSerializer,
    FileUploadUrlRequestSerializer,
)
from apis.services import storage

KEY_INVALID_DETAIL = 'Khoá tệp không hợp lệ.'
OBJECT_NOT_FOUND_DETAIL = 'Không tìm thấy tệp đã tải lên với khoá này.'
OBJECT_TOO_LARGE_DETAIL = 'Tệp vượt quá giới hạn 5MB.'
OBJECT_BAD_CONTENT_TYPE_DETAIL = 'Định dạng tệp không được hỗ trợ.'

KEY_PREFIX = 'uploads/'

# Maps the allowlisted content types to a file extension for the generated key
# -- purely cosmetic (S3 doesn't care), but a `.bin` key is unpleasant to debug
# in a bucket browser.
_EXTENSION_BY_CONTENT_TYPE = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
}

# The server itself is the ONLY thing that mints a key (`FileUploadUrlAPIView`
# below), so confirm validates the client's `key` against that exact minted
# shape rather than a loose `startswith` -- a prefix check also accepts `../`
# traversal, a bare directory, embedded newlines, etc., none of which botocore
# normalises (it would store/HEAD them literally).
#
# The extension alternation is built FROM `_EXTENSION_BY_CONTENT_TYPE.values()`
# rather than hardcoded, so the regex can never silently drift out of sync with
# what minting actually produces: add a content type to one without the other
# and every upload of that type breaks loudly (confirm always rejects it)
# instead of quietly accepting a shape nothing mints.
#
# `\Z`, NOT `$`: Python's `$` also matches immediately before one trailing
# newline, so `re.match(r'...jpg$', 'uploads/<hex>.jpg\n')` SUCCEEDS. `\Z` is
# end-of-string and nothing else. Do not "simplify" it back -- and do not rely
# on `FileConfirmSerializer.key` having sanitised it either: DRF's `CharField`
# strips it only because `trim_whitespace` defaults to True, which is a default
# this module does not control.
_KEY_RE = re.compile(
    r'^' + re.escape(KEY_PREFIX) + r'[0-9a-f]{32}\.('
    + '|'.join(re.escape(ext) for ext in _EXTENSION_BY_CONTENT_TYPE.values())
    + r')\Z'
)


def require_storage():
    if not storage.is_configured():
        raise ServiceUnavailableException()


class FileUploadUrlAPIView(APIView):
    """`POST /api/files/upload-url` -- mints a presigned `PUT` URL.

    Writes nothing. The client must still call `FileConfirmAPIView` after
    uploading to get a readable URL back.
    """

    permission_classes = [AllowAny]
    # Scoped-throttled (only these endpoints, not project-wide -- `apis/`
    # deliberately has no default throttle). See the module docstring for how
    # little this actually guarantees.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'file-upload'

    def post(self, request):
        require_storage()

        serializer = FileUploadUrlRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        content_type = serializer.validated_data['content_type']
        extension = _EXTENSION_BY_CONTENT_TYPE[content_type]
        key = '{}{}.{}'.format(KEY_PREFIX, uuid.uuid4().hex, extension)

        return Response({'data': {
            'upload_url': storage.presign_put(key, content_type),
            'key': key,
            'expires_in': storage.PRESIGN_PUT_TTL_SECONDS,
        }})


class FileConfirmAPIView(APIView):
    """`POST /api/files/confirm` -- verifies the uploaded object, returns its URL.

    This is where the 5MB cap and the content-type allowlist are enforced for
    real: `head()` reads back what is actually in the bucket, rather than
    trusting the `content_type`/`size` the client declared at mint time.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'file-upload'

    def post(self, request):
        require_storage()

        serializer = FileConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        key = serializer.validated_data['key']
        if not _KEY_RE.match(key):
            raise BadRequestException(KEY_INVALID_DETAIL)

        meta = storage.head(key)
        if meta is None:
            raise BadRequestException(OBJECT_NOT_FOUND_DETAIL)
        if meta['content_length'] > MAX_FILE_BYTES:
            raise BadRequestException(OBJECT_TOO_LARGE_DETAIL)
        if meta['content_type'] not in ALLOWED_CONTENT_TYPES:
            raise BadRequestException(OBJECT_BAD_CONTENT_TYPE_DETAIL)

        return Response({'data': {
            'key': key,
            'url': storage.presign_get(key),
            'expires_in': storage.PRESIGN_GET_TTL_SECONDS,
        }})
