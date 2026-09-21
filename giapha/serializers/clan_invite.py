"""Serializers for ClanInvite, `POST /join` and the shared review-note body."""

import datetime

from django.utils import timezone
from rest_framework import serializers

from giapha.models import INVITE_ROLE, ClanInvite

INVITE_DEFAULT_TTL_DAYS = 30


def _default_expires_at():
    """Called fresh per request (DRF calls callable `default`s at
    validation time) -- a module-level constant would freeze the expiry to
    import time. Decision: invites never default to `None` (never-expiring).
    """
    return timezone.now() + datetime.timedelta(days=INVITE_DEFAULT_TTL_DAYS)


class ClanInviteSerializer(serializers.ModelSerializer):
    """`code` is null while `status='pending_approval'` (minted on approval)."""

    person_id = serializers.IntegerField(read_only=True, allow_null=True)
    created_by_id = serializers.IntegerField(read_only=True, allow_null=True)
    approved_by_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = ClanInvite
        fields = (
            'id', 'code', 'role', 'status', 'person_id', 'request_note', 'review_note',
            'created_by_id', 'approved_by_id', 'expires_at', 'max_uses', 'used_count', 'created_at',
        )
        read_only_fields = fields


class ClanInviteCreateSerializer(serializers.Serializer):
    """Input for `POST /clans/{clan_id}/invites`.

    `role` is capped to `INVITE_ROLE` (editor/viewer) -- ownership can never
    be granted through an invite code. `expires_at` always resolves to a real
    datetime (30 days out by default), never `None`/never-expiring.
    """

    role = serializers.ChoiceField(choices=INVITE_ROLE, default='viewer')
    expires_at = serializers.DateTimeField(required=False, default=_default_expires_at)
    max_uses = serializers.IntegerField(required=False, min_value=0, default=0)
    # Pre-bind the invitee to this node (same clan, unclaimed, alive --
    # checked by the view). Forces `max_uses=1`.
    person_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    request_note = serializers.CharField(required=False, allow_blank=True, max_length=255, default='')

    def create(self, validated_data):
        raise NotImplementedError

    def update(self, instance, validated_data):
        raise NotImplementedError


class ReviewNoteSerializer(serializers.Serializer):
    """`{note?}` body of approve/reject endpoints (invites, change requests)."""

    note = serializers.CharField(required=False, allow_blank=True, max_length=255, default='')

    def create(self, validated_data):
        raise NotImplementedError

    def update(self, instance, validated_data):
        raise NotImplementedError


class JoinClanSerializer(serializers.Serializer):
    """Input for `POST /join`."""

    code = serializers.CharField(max_length=12, allow_blank=False)

    def create(self, validated_data):
        raise NotImplementedError

    def update(self, instance, validated_data):
        raise NotImplementedError
