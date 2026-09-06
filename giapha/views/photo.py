"""Presigned S3/R2 upload endpoints for `Person.photo_key` (phase 8).

Django never receives photo bytes. The client asks `photo-upload-url` for a
presigned `PUT`, uploads directly to S3/R2, then confirms with `photo`
(`POST`) so the key is only written after the server itself has verified the
object exists, is under the size cap, and has an allowed content type --
never on the client's say-so. See `giapha/services/storage.py` for why a
presigned `PUT` cannot enforce the size cap up front, and why `head()` at
confirm time is where that cap is actually enforced.

STORAGE UNCONFIGURED -> 503 ON EVERY VIEW IN THIS MODULE (and in
`views/photo_urls.py`), and nowhere else. The rest of the API (plain person
read/write, `/tree`) must keep working on a host with no S3/R2 credentials
set at all.

The batched `POST /clans/{clan_id}/photo-urls` endpoint lives in the
sibling `views/photo_urls.py` -- this file was already at the 200-line
limit (`docs/code-standards.md` -> Files), and that endpoint is clan-scoped
(`IsClanMember`) rather than person-scoped (`IsClanEditor`) like everything
else here, a natural seam. It imports `require_storage` from here rather
than duplicating it.
"""

import logging
import re
import uuid

from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException, ServiceUnavailableException
from giapha.permissions import IsClanEditor
from giapha.selectors.person import get_person_or_none
from giapha.selectors.revision import record
from giapha.serializers.person import PersonReadSerializer
from giapha.serializers.photo import (
    ALLOWED_CONTENT_TYPES,
    MAX_PHOTO_BYTES,
    PhotoConfirmSerializer,
    PhotoUploadUrlRequestSerializer,
)
from giapha.services import storage

logger = logging.getLogger(__name__)

PERSON_NOT_FOUND = 'Không tìm thấy thành viên.'
KEY_PREFIX_MISMATCH_DETAIL = 'Khoá ảnh không thuộc về thành viên này.'
OBJECT_NOT_FOUND_DETAIL = 'Không tìm thấy ảnh đã tải lên với khoá này.'
OBJECT_TOO_LARGE_DETAIL = 'Ảnh vượt quá giới hạn 5MB.'
OBJECT_BAD_CONTENT_TYPE_DETAIL = 'Định dạng ảnh không được hỗ trợ.'

# Maps the allowlisted content types to a file extension for the generated
# key -- purely cosmetic (S3 doesn't care), but a `.bin` key is unpleasant to
# debug in a bucket browser.
_EXTENSION_BY_CONTENT_TYPE = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
}

# H1: the confirm step used to accept ANY key that merely `.startswith()`
# the clan/person prefix, which also accepts `../` traversal, a bare
# directory, embedded newlines, etc -- botocore does not normalise any of
# that, so it was stored/HEADed/deleted literally. The server itself is the
# only thing that ever mints a key (`PersonPhotoUploadUrlAPIView.post`,
# below), so the fix is to validate the client's `key` against that exact
# minted shape instead of a loose prefix: `giapha/{clan_id}/{person_id}/`
# followed by a bare 32-hex UUID and one of the allowlisted extensions,
# nothing else. The extension alternation is built FROM
# `_EXTENSION_BY_CONTENT_TYPE.values()` rather than hardcoded, so the regex
# can never silently drift out of sync with what minting actually produces
# -- if a new content type/extension is ever added to one without the
# other, every upload of that type breaks loudly (confirm always rejects
# it) instead of quietly accepting a shape nothing actually mints.
_KEY_RE = re.compile(
    r'^giapha/(\d+)/(\d+)/[0-9a-f]{32}\.('
    + '|'.join(re.escape(ext) for ext in _EXTENSION_BY_CONTENT_TYPE.values())
    + r')$'
)


def require_storage():
    """Shared by this module and `views/photo_urls.py`."""
    if not storage.is_configured():
        raise ServiceUnavailableException()


def _key_prefix(clan_id, person_id):
    """`giapha/{clan_id}/{person_id}/` -- every photo key lives under this
    prefix (phase-08 spec). Checking a confirmed key against this exact
    string is what stops a client from confirming a key that belongs to
    another clan or another person in the same clan.
    """
    return 'giapha/{}/{}/'.format(clan_id, person_id)


def _swallow_delete(key):
    """Delete `key`, logging (not raising) on failure. Deliberate broad
    catch -- the only one in this module, and an intentional exception to
    the "no blanket except" rule in `docs/code-standards.md`: this call
    always follows a photo_key write/clear that has ALREADY succeeded, so a
    failed delete here must not turn that success into a 500 for the
    client. It leaves an orphaned object in the bucket instead -- accepted
    at MVP per the phase-08 spec's risk assessment (no cleanup job yet).
    """
    try:
        storage.delete(key)
    except Exception:
        logger.exception('Không xoá được ảnh cũ tại key=%s', key)


class PersonPhotoUploadUrlAPIView(APIView):
    """`POST` -- editor only. Mints a presigned `PUT` URL; writes nothing to
    the database. The client must still call `PersonPhotoAPIView.post` (the
    confirm step) after uploading for the photo to actually attach.
    """

    permission_classes = [IsAuthenticated, IsClanEditor]

    def post(self, request, clan_id, person_id):
        require_storage()
        person = get_person_or_none(clan_id, person_id)
        if person is None:
            raise NotFound(PERSON_NOT_FOUND)

        serializer = PhotoUploadUrlRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        content_type = serializer.validated_data['content_type']
        extension = _EXTENSION_BY_CONTENT_TYPE[content_type]
        key = '{}{}.{}'.format(_key_prefix(clan_id, person_id), uuid.uuid4().hex, extension)

        upload_url = storage.presign_put(key, content_type)
        return Response({'data': {
            'upload_url': upload_url,
            'key': key,
            'expires_in': storage.PRESIGN_PUT_TTL_SECONDS,
        }})


class PersonPhotoAPIView(APIView):
    """`POST` confirms an already-uploaded object as `person.photo_key`;
    `DELETE` removes the current photo. Both editor-only.
    """

    permission_classes = [IsAuthenticated, IsClanEditor]

    def post(self, request, clan_id, person_id):
        require_storage()
        person = get_person_or_none(clan_id, person_id)
        if person is None:
            raise NotFound(PERSON_NOT_FOUND)

        serializer = PhotoConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        key = serializer.validated_data['key']
        match = _KEY_RE.match(key)
        # Also what rejects a key belonging to another clan, or another
        # person in the SAME clan -- both fail the id-tuple comparison even
        # though the shape itself matches. A key that isn't even shaped like
        # something this server minted (traversal, a bare directory,
        # embedded newlines, wrong extension, ...) fails the regex outright.
        if not match or (int(match.group(1)), int(match.group(2))) != (clan_id, person_id):
            raise BadRequestException(KEY_PREFIX_MISMATCH_DETAIL)

        meta = storage.head(key)
        if meta is None:
            raise BadRequestException(OBJECT_NOT_FOUND_DETAIL)
        if meta['content_length'] > MAX_PHOTO_BYTES:
            raise BadRequestException(OBJECT_TOO_LARGE_DETAIL)
        if meta['content_type'] not in ALLOWED_CONTENT_TYPES:
            raise BadRequestException(OBJECT_BAD_CONTENT_TYPE_DETAIL)

        old_key = person.photo_key
        with transaction.atomic():
            record(person, actor=request.user, action='update')
            person.photo_key = key
            person.save(update_fields=['photo_key'])

        # New key is written FIRST, old object deleted AFTER (phase-08 spec):
        # a failed delete only leaves garbage, it never loses the new photo.
        if old_key and old_key != key:
            _swallow_delete(old_key)

        # `with_photo_url`: this confirm response is a detail-shaped
        # response (H3) -- the client just attached a photo and expects to
        # see it, same as `GET`/`PATCH .../persons/{pid}`.
        return Response({'data': PersonReadSerializer(person, context={'with_photo_url': True}).data})

    def delete(self, request, clan_id, person_id):
        require_storage()
        person = get_person_or_none(clan_id, person_id)
        if person is None:
            raise NotFound(PERSON_NOT_FOUND)

        old_key = person.photo_key
        with transaction.atomic():
            record(person, actor=request.user, action='update')
            person.photo_key = ''
            person.save(update_fields=['photo_key'])

        if old_key:
            _swallow_delete(old_key)

        return Response(status=status.HTTP_204_NO_CONTENT)
