"""Request bodies for the `/v1/family` mutation endpoints (spec §8.2–8.5).

Shape/type only. Whether the ids exist, whether the slot is free, whether a
cycle would form -- all of that is `services.family_rules`, run by the view
against the loaded graph.
"""

from rest_framework import serializers

from giapha.models import FAMILY_PARENT_REL, FAMILY_SPOUSE_REL
from giapha.serializers.family_draft import PersonDraftSerializer

_PARENT_RELS = [value for value, _ in FAMILY_PARENT_REL]
_SPOUSE_RELS = [value for value, _ in FAMILY_SPOUSE_REL]
ADD_RELATIVE_KINDS = ('father', 'mother', 'spouse', 'child', 'sibling')


def _uuid(source, **kwargs):
    kwargs.setdefault('error_messages', {'invalid': 'Id không đúng định dạng UUID.'})
    return serializers.UUIDField(source=source, **kwargs)


class SetParentBodySerializer(serializers.Serializer):
    childId = _uuid('child_id')
    slot = serializers.ChoiceField(choices=['father', 'mother'])
    # `null` = clearFather / clearMother.
    parentId = _uuid('parent_id', allow_null=True)
    rel = serializers.ChoiceField(choices=_PARENT_RELS, default='blood')


class LinkSpouseBodySerializer(serializers.Serializer):
    aId = _uuid('a_id')
    bId = _uuid('b_id')
    type = serializers.ChoiceField(choices=_SPOUSE_RELS, default='married')


class UnlinkSpouseBodySerializer(serializers.Serializer):
    aId = _uuid('a_id')
    bId = _uuid('b_id')


class LinkChildBodySerializer(serializers.Serializer):
    parentId = _uuid('parent_id')
    childId = _uuid('child_id')
    otherParentId = _uuid('other_parent_id', required=False, allow_null=True, default=None)


class AddRelativeBodySerializer(serializers.Serializer):
    anchorId = _uuid('anchor_id')
    kind = serializers.ChoiceField(choices=ADD_RELATIVE_KINDS)
    person = PersonDraftSerializer()
    # Only meaningful for kind=child (which other parent to fill in).
    otherParentId = _uuid('other_parent_id', required=False, allow_null=True, default=None)


class SelfBodySerializer(serializers.Serializer):
    personId = _uuid('person_id', allow_null=True)


class GioEventBodySerializer(serializers.Serializer):
    eventId = serializers.CharField(source='event_id', max_length=64, allow_null=True, allow_blank=True)
