"""Request shape of `PUT /v1/family/import` (spec §12).

Only the envelope is strict: `importKey`, a list of person OBJECTS each with
a string `id`, at most `FAMILY_MAX_PERSONS` of them. Everything inside a
person is repaired, not rejected -- see `services.family_import_fields`.
"""

from django.conf import settings
from rest_framework import serializers


class FamilyImportSerializer(serializers.Serializer):
    importKey = serializers.CharField(max_length=36, source='import_key')
    selfId = serializers.CharField(max_length=64, required=False, allow_null=True, source='self_id', default=None)
    persons = serializers.ListField(child=serializers.DictField(), allow_empty=True)

    def validate_persons(self, persons):
        limit = settings.FAMILY_MAX_PERSONS
        if len(persons) > limit:
            raise serializers.ValidationError('Gia phả vượt quá giới hạn {} người.'.format(limit))
        for index, person in enumerate(persons):
            person_id = person.get('id')
            if not isinstance(person_id, str) or not person_id or len(person_id) > 64:
                raise serializers.ValidationError('Người thứ {} thiếu id hợp lệ.'.format(index + 1))
        return persons

    def create(self, validated_data):
        raise NotImplementedError

    def update(self, instance, validated_data):
        raise NotImplementedError
