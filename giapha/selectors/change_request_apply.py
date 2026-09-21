"""Apply an approved ChangeRequest through the shared write path.

`target_ids(cr)` says which persons a proposal touches (for reviewer scope
checks); `staleness(cr)` compares the target with the proposal's base;
`apply_change_request(cr, reviewer)` dispatches on `cr.action` to
`selectors.person_write` / `selectors.marriage_write`, so an applied
proposal gets the same rules, revision (actor = reviewer, linked to `cr`)
and generation recompute as a direct edit.
"""

import json

from giapha.selectors.marriage import get_marriage_or_none
from giapha.selectors.marriage_write import apply_marriage_create, apply_marriage_delete, apply_marriage_update
from giapha.selectors.person import get_person_or_none
from giapha.selectors.person_write import apply_person_create_many, apply_person_delete, apply_person_update
from giapha.serializers.change_request import validated_payload
from giapha.services.person_rules import PersonValidationError

STALE_CHANGED = 'changed'
STALE_GONE = 'gone'
TARGET_GONE_DETAIL = 'Người hoặc hôn nhân được đề xuất sửa không còn tồn tại.'


def payload_of(cr):
    return json.loads(cr.payload_json or '{}')


def live_target_person(cr):
    return get_person_or_none(cr.clan_id, cr.target_person_id) if cr.target_person_id else None


def live_target_marriage(cr):
    return get_marriage_or_none(cr.clan_id, cr.target_marriage_id) if cr.target_marriage_id else None


def target_ids(cr):
    """`(person_ids, any_of)` -- the persons a reviewer must be able to write.
    New persons are judged by their parents, marriages by either partner.
    """
    if cr.action in ('update_person', 'delete_person'):
        return [cr.target_person_id], False
    payload = payload_of(cr)
    if cr.action == 'create_person':
        return [payload.get('father_id'), payload.get('mother_id')], True
    if cr.action == 'create_marriage':
        return [payload.get('husband_id'), payload.get('wife_id')], True
    marriage = cr.target_marriage
    return ([marriage.husband_id, marriage.wife_id] if marriage else []), True


def staleness(cr):
    """None when fresh; `STALE_GONE` when the target no longer exists (cannot
    be overridden); `STALE_CHANGED` when it was edited after the proposal.
    """
    if cr.action in ('update_person', 'delete_person'):
        person = live_target_person(cr)
        if person is None:
            return STALE_GONE
        if cr.base_version is not None:
            if person.version != cr.base_version:
                return STALE_CHANGED
        elif cr.base_updated_at and person.updated_at > cr.base_updated_at:
            return STALE_CHANGED
    elif cr.action in ('update_marriage', 'delete_marriage') and live_target_marriage(cr) is None:
        return STALE_GONE
    return None


def apply_change_request(cr, reviewer, expected_version=None):
    """Apply `cr`; returns the written Person/Marriage (None for deletes).
    Raises `PersonValidationError` (rule violation) or DRF `ValidationError`
    (payload no longer valid) -- the caller answers 400, `cr` stays pending.
    """
    payload = payload_of(cr)
    clan_id = cr.clan_id
    action = cr.action

    if action == 'create_person':
        data = validated_payload(action, payload)
        return apply_person_create_many(clan_id, [data], reviewer, change_request=cr)[0]
    if action in ('update_person', 'delete_person'):
        person = live_target_person(cr)
        if person is None:
            raise PersonValidationError(TARGET_GONE_DETAIL)
        if action == 'delete_person':
            apply_person_delete(person, reviewer, change_request=cr)
            return None
        data = validated_payload(action, payload, instance=person)
        # Locked version check closes the gap between `staleness()` (unlocked
        # read) and the write (review M4); `None` when the reviewer overrides.
        return apply_person_update(clan_id, person, data, reviewer, change_request=cr,
                                   expected_version=expected_version)
    if action == 'create_marriage':
        return apply_marriage_create(clan_id, validated_payload(action, payload))

    marriage = live_target_marriage(cr)
    if marriage is None:
        raise PersonValidationError(TARGET_GONE_DETAIL)
    if action == 'delete_marriage':
        apply_marriage_delete(marriage)
        return None
    return apply_marriage_update(marriage, validated_payload(action, payload, instance=marriage))
