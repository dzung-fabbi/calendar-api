"""Person read/write serializers, split per phase-3 spec so a future public
(phase 9) serializer can subclass/reuse `PersonReadSerializer` without
inheriting any write-path fields.
"""

from rest_framework import serializers

from giapha.models import Person, PersonRevision

_WRITE_FIELDS = (
    # `generation` is deliberately absent -- it is derived state (see
    # `services.tree.compute_generations`), never client-writable. A client
    # posting `generation: 999` is silently ignored, not a validation error.
    'ho_ten', 'ten_huy', 'ten_tu', 'ten_hieu', 'thuy_hieu', 'gioi_tinh',
    'father_id', 'mother_id', 'parent_kind',
    'branch', 'birth_order', 'is_truong',
    'birth_solar', 'birth_lunar_day', 'birth_lunar_month', 'birth_lunar_leap',
    'death_solar', 'death_lunar_day', 'death_lunar_month', 'death_lunar_leap',
    'que_quan', 'nghe_nghiep', 'tieu_su', 'photo_key',
    'mo_phan_lat', 'mo_phan_lng', 'mo_phan_note',
)

_READ_FIELDS = (
    'id', 'ho_ten', 'ten_huy', 'ten_tu', 'ten_hieu', 'thuy_hieu', 'gioi_tinh',
    'father_id', 'father_name', 'mother_id', 'mother_name', 'parent_kind',
    'generation', 'branch', 'birth_order', 'is_truong',
    'birth_solar', 'birth_lunar_day', 'birth_lunar_month', 'birth_lunar_leap',
    'death_solar', 'death_lunar_day', 'death_lunar_month', 'death_lunar_leap',
    'que_quan', 'nghe_nghiep', 'tieu_su', 'photo_key',
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

    class Meta:
        model = Person
        fields = _READ_FIELDS
        read_only_fields = _READ_FIELDS

    def get_father_name(self, obj):
        return obj.father.ho_ten if obj.father_id else None

    def get_mother_name(self, obj):
        return obj.mother.ho_ten if obj.mother_id else None


class PersonRevisionSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True, default=None)

    class Meta:
        model = PersonRevision
        fields = ('id', 'action', 'actor_username', 'payload_json', 'created_at')
        read_only_fields = fields
