"""Serializers for Clan, ClanMember and ClanInvite."""

import datetime

from django.utils import timezone
from rest_framework import serializers

from giapha.models import CLAN_ROLE, INVITE_ROLE, Clan, ClanInvite, ClanMember
from giapha.selectors.clan import clan_role_for

INVITE_DEFAULT_TTL_DAYS = 30


def _default_expires_at():
    """Called fresh per request (DRF calls callable `default`s at
    validation time) -- a module-level constant would freeze the expiry to
    import time. Decision: invites never default to `None` (never-expiring).
    """
    return timezone.now() + datetime.timedelta(days=INVITE_DEFAULT_TTL_DAYS)


class ClanSerializer(serializers.ModelSerializer):
    """Used for create, read and partial update.

    `public_slug` is stripped from the output for anyone but the clan's
    owner -- viewers and editors must not see it (phase-9 public page slug).
    """

    class Meta:
        model = Clan
        fields = (
            'id', 'ten_ho', 'thuy_to', 'mo_ta', 'visibility',
            'public_slug', 'hide_living_details', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'public_slug', 'created_at', 'updated_at')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._caller_is_owner(instance):
            data.pop('public_slug', None)
        return data

    def _caller_is_owner(self, instance):
        roles = self.context.get('roles')
        if roles is not None:
            return roles.get(instance.id) == 'owner'

        request = self.context.get('request')
        if request is None:
            return False
        cache = getattr(request, '_giapha_role_cache', {})
        role = cache.get(instance.id)
        if role is None:
            role = clan_role_for(request.user, instance.id)
        return role == 'owner'


class ClanMemberSerializer(serializers.ModelSerializer):
    """`email` is only shown to the clan's owner -- every other role sees
    `username`/`role`/`joined_at` only. The roster is `IsClanMember` (any
    role), so without this gate a viewer who joined via an invite code could
    harvest every member's email address.
    """

    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = ClanMember
        fields = ('user_id', 'username', 'email', 'role', 'joined_at')
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._caller_is_owner(instance):
            data.pop('email', None)
        return data

    def _caller_is_owner(self, instance):
        request = self.context.get('request')
        if request is None:
            return False
        cache = getattr(request, '_giapha_role_cache', {})
        role = cache.get(instance.clan_id)
        if role is None:
            role = clan_role_for(request.user, instance.clan_id)
        return role == 'owner'


class ClanMemberRoleUpdateSerializer(serializers.Serializer):
    """Input for `PATCH /clans/{clan_id}/members/{user_id}`."""

    role = serializers.ChoiceField(choices=CLAN_ROLE)

    def create(self, validated_data):
        raise NotImplementedError

    def update(self, instance, validated_data):
        raise NotImplementedError


class ClanInviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClanInvite
        fields = ('id', 'code', 'role', 'expires_at', 'max_uses', 'used_count', 'created_at')
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
