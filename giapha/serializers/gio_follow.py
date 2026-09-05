"""Shapes for `clans/{id}/toi-la` and `clans/{id}/gio-follows`.

The read serializers describe plain dicts built by the view (same arrangement
as `serializers/gio.py`) rather than model instances -- the follow list is a
*resolved* view over two tables plus an in-memory ancestor walk, so there is
no single row to serialise.
"""

from rest_framework import serializers

# Why a person is (or is not) on the resolved list. Three values, because
# there are three states and a client that cannot tell them apart cannot
# explain to the user why an ancestor vanished from their reminders.
FOLLOW_SOURCE = (
    ('truc-he', 'Tổ tiên trực hệ'),   # default on: ancestor of the caller's node
    ('thu-cong', 'Tự thêm'),          # override enabled=True
    ('da-bo', 'Đã bỏ'),               # override enabled=False
)


class MemberBindingSerializer(serializers.Serializer):
    """`GET/PUT /clans/{id}/toi-la` payload. `data` is null when unbound."""

    person_id = serializers.IntegerField()
    ho_ten = serializers.CharField()


class MemberBindingWriteSerializer(serializers.Serializer):
    """`PUT /clans/{id}/toi-la` body.

    Only `person_id`: the user is always `request.user`. Accepting a user id
    here would let an owner bind on someone else's behalf, which the MVP
    deliberately does not allow.
    """

    person_id = serializers.IntegerField()


class GioFollowItemSerializer(serializers.Serializer):
    person_id = serializers.IntegerField()
    ho_ten = serializers.CharField()
    thuy_hieu = serializers.CharField(allow_blank=True)
    generation = serializers.IntegerField(allow_null=True)
    lunar = serializers.DictField(child=serializers.IntegerField())
    # The resolved answer; `source` is the reason for it.
    followed = serializers.BooleanField()
    source = serializers.ChoiceField(choices=FOLLOW_SOURCE)


class GioFollowListSerializer(serializers.Serializer):
    items = GioFollowItemSerializer(many=True)
    # False when the caller has no `ClanMember.person` yet: the list is then
    # only their manual additions, and the client should prompt them to say
    # who they are in the tree rather than show an empty screen.
    bound = serializers.BooleanField()
    # True when the clan exceeded `MAX_CLAN_PERSONS` and the tail of the
    # deceased list was dropped -- same key, same meaning as `GET /tree` and
    # `GET /lich-gio`. A clan at the ceiling would otherwise lose ancestors
    # off this screen with no sign that anything is missing.
    truncated = serializers.BooleanField()


class GioFollowWriteSerializer(serializers.Serializer):
    """`PUT /clans/{id}/gio-follows/{person_id}` body. Required, no default:
    the stored row must always be an explicit statement (see the model).
    """

    enabled = serializers.BooleanField()
