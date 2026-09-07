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

    `visibility` is READ-ONLY here (security fix, phase-9 review H2):
    `POST`/`DELETE /clans/{id}/public-link` (`views.clan.
    ClanPublicLinkAPIView`) are the ONLY sanctioned way to flip it, because
    that view's `atomic()` block keeps `visibility` and `public_slug` in
    lockstep -- enable always mints a fresh slug, revoke always clears the
    old one. A writable `visibility` here let `PATCH /clans/{id}` toggle
    sharing through a second, unguarded path: `PATCH {"visibility":
    "private"}` never touched `public_slug`, so a later `PATCH
    {"visibility":"public_link"}` re-armed the SAME leaked slug instead of
    minting a new one -- silently defeating the "revoke means the old link
    is dead forever" guarantee. It also let a clan reach
    `visibility='public_link'` with `public_slug=NULL`, the exact half-state
    `ClanPublicLinkAPIView`'s `atomic()` exists to prevent. No client
    depends on setting `visibility` via `PATCH` (nothing but the toggle view
    ever did it correctly).
    """

    class Meta:
        model = Clan
        fields = (
            'id', 'ten_ho', 'thuy_to', 'mo_ta', 'visibility',
            'public_slug', 'hide_living_details', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'visibility', 'public_slug', 'created_at', 'updated_at')

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
    """`email` AND `username` are only shown to the clan's owner -- every other
    role sees `user_id`/`display_name`/`role`/`joined_at`. The roster is
    `IsClanMember` (any role), so without this gate a viewer who joined via an
    invite code could harvest every member's email address.

    WHY `username` IS GATED TOO, not just `email`: account registration
    (`apis/views/auth_register.py`) stores the user's email address AS the
    username. Leaving `username` ungated therefore hands every viewer exactly
    the addresses the `email` gate exists to protect -- the gate would still be
    there, and it would do nothing. Gating one column but not its duplicate is
    the whole bug.

    `display_name` replaces it for non-owners so a roster still has something
    human to show. It falls back to a masked username for accounts with no name
    set, rather than to the raw value.
    """

    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = ClanMember
        fields = ('user_id', 'username', 'display_name', 'email', 'role', 'joined_at')
        read_only_fields = fields

    def get_display_name(self, instance):
        user = instance.user
        full_name = '{} {}'.format(user.first_name, user.last_name).strip()
        if full_name:
            return full_name
        # No name on the account. Show enough to tell two rows apart without
        # reproducing the address: `nguoi.dung@example.com` -> `ngu***`.
        local_part = (user.username or '').split('@')[0]
        return '{}***'.format(local_part[:3]) if local_part else ''

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._caller_is_owner(instance):
            data.pop('email', None)
            data.pop('username', None)
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
