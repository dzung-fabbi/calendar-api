"""Serializers for Clan and ClanMember. Invite/join shapes: `serializers/clan_invite.py`."""

from rest_framework import serializers

from giapha.models import CLAN_ROLE, Clan, ClanMember
from giapha.selectors.clan import clan_role_for

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
        role = self._caller_role(instance)
        if role != 'owner':
            data.pop('public_slug', None)
        # The caller's own role: without it a client listing N clans needs N
        # `GET /members` calls just to label its cards.
        data['role'] = role
        return data

    def _caller_role(self, instance):
        roles = self.context.get('roles')
        if roles is not None:
            return roles.get(instance.id)

        request = self.context.get('request')
        if request is None:
            return None
        cache = getattr(request, '_giapha_role_cache', {})
        role = cache.get(instance.id)
        if role is None:
            role = clan_role_for(request.user, instance.id)
        return role


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
        # `person_id` + `person_verified`: approvers find pending self-claims
        # here (`person_id` set, `person_verified` false).
        fields = (
            'user_id', 'username', 'display_name', 'email', 'role', 'person_id', 'person_verified',
            'scope_root_person_id', 'joined_at',
        )
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
    """Input for `PATCH /clans/{clan_id}/members/{user_id}`. `role` and/or
    `scope_root_person_id` (phase 6: branch root for an editor; null clears).
    """

    role = serializers.ChoiceField(choices=CLAN_ROLE, required=False)
    scope_root_person_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Cần role hoặc scope_root_person_id.')
        return attrs

    def create(self, validated_data):
        raise NotImplementedError

    def update(self, instance, validated_data):
        raise NotImplementedError

