"""Request bodies for `/v1/family/links/*` and `POST /v1/family/clans`
(plan 260919 phase 4). camelCase on the wire like the rest of `/v1/family`.
"""

from rest_framework import serializers

MAX_LINK_PAIRS = 200


class _NoSave(serializers.Serializer):
    def create(self, validated_data):
        raise NotImplementedError

    def update(self, instance, validated_data):
        raise NotImplementedError


class ClanIdQuerySerializer(_NoSave):
    clanId = serializers.IntegerField(min_value=1)


class LinkPairSerializer(_NoSave):
    personId = serializers.UUIDField()
    clanPersonId = serializers.IntegerField(min_value=1)


class LinkCreateSerializer(_NoSave):
    clanId = serializers.IntegerField(min_value=1)
    pairs = LinkPairSerializer(many=True, allow_empty=False, max_length=MAX_LINK_PAIRS)


class ClanBootstrapSerializer(_NoSave):
    rootPersonId = serializers.UUIDField()
    tenHo = serializers.CharField(max_length=255)
    thuyTo = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')


class LinkImportSerializer(_NoSave):
    clanId = serializers.IntegerField(min_value=1)
    clanPersonIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1), allow_empty=False, max_length=MAX_LINK_PAIRS,
    )


class LinkContributeSerializer(_NoSave):
    personId = serializers.UUIDField()
    clanId = serializers.IntegerField(min_value=1)
    fatherClanPersonId = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    motherClanPersonId = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')
