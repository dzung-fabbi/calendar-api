"""Person read/write serializers, split per phase-3 spec so a future public
(phase 9) serializer can subclass/reuse `PersonReadSerializer` without
inheriting any write-path fields.
"""

import logging

from rest_framework import serializers

from giapha.models import Person, PersonRevision
from giapha.services import storage

logger = logging.getLogger(__name__)

_WRITE_FIELDS = (
    # `generation` is deliberately absent -- it is derived state (see
    # `services.tree.compute_generations`), never client-writable. A client
    # posting `generation: 999` is silently ignored, not a validation error.
    #
    # `photo_key` is ALSO deliberately absent (phase 8). Letting a client
    # PATCH it directly would let them point a person at an arbitrary S3 key
    # -- including one from another clan's prefix, or one that was never
    # uploaded at all. The only legal way to set it is the presigned-upload
    # confirm step (`views.photo.PersonPhotoAPIView.post`), which verifies
    # the key's exact minted shape and HEADs the object before writing --
    # and `services.revision._EXCLUDED_FIELDS` keeps `POST /restore` from
    # being a second, unchecked way to set it (it's excluded on both the
    # snapshot and restore side, so no revision payload can move it either).
    'ho_ten', 'ten_huy', 'ten_tu', 'ten_hieu', 'thuy_hieu', 'gioi_tinh',
    'father_id', 'mother_id', 'parent_kind',
    'branch', 'birth_order', 'is_truong',
    'birth_solar', 'birth_lunar_day', 'birth_lunar_month', 'birth_lunar_leap',
    'death_solar', 'death_lunar_day', 'death_lunar_month', 'death_lunar_leap',
    'que_quan', 'nghe_nghiep', 'tieu_su',
    'mo_phan_lat', 'mo_phan_lng', 'mo_phan_note',
)

# `photo_key` is deliberately NOT a read field (L2): it's a raw bucket path,
# internal storage layout that a client has no use for -- `photo_url` (a
# time-limited presigned link) is the real need, and this matches the
# deliberate choice to give `/tree` only `has_photo` (`services.tree.
# node_from_row`), never the key or a URL.
_READ_FIELDS = (
    'id', 'ho_ten', 'ten_huy', 'ten_tu', 'ten_hieu', 'thuy_hieu', 'gioi_tinh',
    'father_id', 'father_name', 'mother_id', 'mother_name', 'parent_kind',
    'generation', 'branch', 'birth_order', 'is_truong',
    'birth_solar', 'birth_lunar_day', 'birth_lunar_month', 'birth_lunar_leap',
    'death_solar', 'death_lunar_day', 'death_lunar_month', 'death_lunar_leap',
    'que_quan', 'nghe_nghiep', 'tieu_su', 'photo_url',
    'mo_phan_lat', 'mo_phan_lng', 'mo_phan_note',
    'is_deleted', 'created_at', 'updated_at',
)


class PersonWriteSerializer(serializers.ModelSerializer):
    """Input for create/update. `father_id`/`mother_id` are plain ids --
    same-clan membership and cycle-safety are checked in
    `services.person_rules`, not here; this layer only checks shape/type.
    """

    father_id = serializers.IntegerField(required=False, allow_null=True)
    mother_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Person
        fields = _WRITE_FIELDS


class PersonReadSerializer(serializers.ModelSerializer):
    """Output shape. Embeds `father_name`/`mother_name` so clients don't
    need a second request just to render a name instead of a bare id.
    """

    father_id = serializers.IntegerField(read_only=True)
    mother_id = serializers.IntegerField(read_only=True)
    father_name = serializers.SerializerMethodField()
    mother_name = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Person
        fields = _READ_FIELDS
        read_only_fields = _READ_FIELDS

    def get_father_name(self, obj):
        return obj.father.ho_ten if obj.father_id else None

    def get_mother_name(self, obj):
        return obj.mother.ho_ten if obj.mother_id else None

    def get_photo_url(self, obj):
        """Presigned GET, TTL 1h (`services.storage.PRESIGN_GET_TTL_SECONDS`).
        `None` whenever there is nothing to show, storage isn't configured,
        OR the caller didn't ask for it (see below) -- this field must never
        raise up into a plain person read just because S3/R2 credentials
        aren't set on this host (phase 8 decision: only the dedicated photo
        endpoints 503), or because presigning itself failed (H3/L4: any
        `botocore` error here is logged and swallowed -- a broken photo link
        must not turn an otherwise-fine person read into a 500).

        Opt-in via `context={'with_photo_url': True}` (H3): the spec scopes
        `photo_url` to the DETAIL response only. Presigning is local HMAC
        (~0.3ms, no network -- see `services.tree`'s M1 fix for the same
        point) so the cost is CPU + response size, not I/O, but a paginated
        list of up to 200 rows (`views.person_list`) still has no business
        paying it: nothing there renders the URL, and it would make the
        `PHOTO_URLS_MAX_IDS` cap on the batched endpoint pointless. Detail
        call sites (`views.person.PersonDetailAPIView.get`/`.patch`,
        `views.photo.PersonPhotoAPIView.post`) pass the context; list/
        bulk-create call sites (`views.person_list`) don't.
        """
        if not obj.photo_key or not self.context.get('with_photo_url'):
            return None
        if not storage.is_configured():
            return None
        try:
            return storage.presign_get(obj.photo_key)
        except Exception:
            logger.warning('Không tạo được photo_url cho person_id=%s', obj.id, exc_info=True)
            return None


class PersonRevisionSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True, default=None)

    class Meta:
        model = PersonRevision
        fields = ('id', 'action', 'actor_username', 'payload_json', 'created_at')
        read_only_fields = fields
