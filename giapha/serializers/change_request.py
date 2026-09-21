"""Serializers for ChangeRequest + the payload validator shared by create
(junk never enters the queue) and approve (the tree may have moved since).
"""

import json

from rest_framework import serializers

from giapha.models import CHANGE_REQUEST_ACTION, ChangeRequest
from giapha.serializers.marriage import MarriageSerializer
from giapha.serializers.person import PersonWriteSerializer

PERSON_TARGET_ACTIONS = ('update_person', 'delete_person')
MARRIAGE_TARGET_ACTIONS = ('update_marriage', 'delete_marriage')
EMPTY_PAYLOAD_DETAIL = 'Đề xuất chưa có thay đổi nào.'


def validated_payload(action, payload, instance=None):
    """`validated_data` for `payload` under `action`'s write serializer.

    Raises DRF `ValidationError` (-> 400). Delete actions carry no payload.
    """
    if action == 'create_person':
        serializer = PersonWriteSerializer(data=payload)
    elif action == 'update_person':
        serializer = PersonWriteSerializer(instance, data=payload, partial=True)
    elif action == 'create_marriage':
        serializer = MarriageSerializer(data=payload)
    elif action == 'update_marriage':
        serializer = MarriageSerializer(instance, data=payload, partial=True)
    else:
        return {}
    serializer.is_valid(raise_exception=True)
    if not serializer.validated_data:
        raise serializers.ValidationError({'payload': [EMPTY_PAYLOAD_DETAIL]})
    return serializer.validated_data


class ChangeRequestCreateSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=CHANGE_REQUEST_ACTION)
    target_person_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    target_marriage_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    payload = serializers.DictField(required=False, default=dict)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500, default='')

    def validate(self, attrs):
        action = attrs['action']
        if action in PERSON_TARGET_ACTIONS and attrs['target_person_id'] is None:
            raise serializers.ValidationError({'target_person_id': ['Bắt buộc với hành động này.']})
        if action in MARRIAGE_TARGET_ACTIONS and attrs['target_marriage_id'] is None:
            raise serializers.ValidationError({'target_marriage_id': ['Bắt buộc với hành động này.']})
        return attrs

    def create(self, validated_data):
        raise NotImplementedError

    def update(self, instance, validated_data):
        raise NotImplementedError


class ChangeRequestApproveSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=500, default='')
    override_stale = serializers.BooleanField(required=False, default=False)

    def create(self, validated_data):
        raise NotImplementedError

    def update(self, instance, validated_data):
        raise NotImplementedError


class ChangeRequestRejectSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=500)

    def create(self, validated_data):
        raise NotImplementedError

    def update(self, instance, validated_data):
        raise NotImplementedError


class ChangeRequestSerializer(serializers.ModelSerializer):
    proposer_id = serializers.IntegerField(read_only=True, allow_null=True)
    reviewer_id = serializers.IntegerField(read_only=True, allow_null=True)
    target_person_id = serializers.IntegerField(read_only=True, allow_null=True)
    target_marriage_id = serializers.IntegerField(read_only=True, allow_null=True)
    payload = serializers.SerializerMethodField()

    class Meta:
        model = ChangeRequest
        fields = (
            'id', 'action', 'status', 'proposer_id', 'target_person_id', 'target_marriage_id',
            'payload', 'proposer_note', 'base_updated_at', 'base_version', 'reviewer_id', 'review_note',
            'created_at', 'reviewed_at',
        )
        read_only_fields = fields

    def get_payload(self, obj):
        return json.loads(obj.payload_json or '{}')
