"""The ONE write path for clan marriages -- shared by the marriage views and
change-request approval (see `selectors/person_write.py` for the rationale).

Raises `PersonValidationError` for every rule violation; callers own
permission checks and turn the error into a 400.
"""

from django.db import IntegrityError, transaction

from giapha.models import Marriage
from giapha.selectors.marriage import next_order_for_husband, orders_for_husband
from giapha.selectors.person import get_person_or_none
from giapha.services.person_rules import (
    PersonValidationError,
    validate_marriage_distinct,
    validate_marriage_order_unique,
)

PARTNER_NOT_IN_CLAN = 'Chồng và vợ phải thuộc dòng họ này.'
DUPLICATE_MARRIAGE_DETAIL = 'Cặp vợ chồng này đã tồn tại.'
_MUTABLE_FIELDS = ('order', 'status', 'note')


def apply_marriage_create(clan_id, data):
    husband_id, wife_id = data['husband_id'], data['wife_id']
    if get_person_or_none(clan_id, husband_id) is None or get_person_or_none(clan_id, wife_id) is None:
        raise PersonValidationError(PARTNER_NOT_IN_CLAN)

    order = data['order'] if data.get('order') is not None else next_order_for_husband(husband_id)
    validate_marriage_distinct(husband_id, wife_id)
    validate_marriage_order_unique(orders_for_husband(husband_id), order)
    try:
        with transaction.atomic():
            return Marriage.objects.create(
                husband_id=husband_id, wife_id=wife_id, order=order,
                status=data['status'], note=data.get('note', ''),
            )
    except IntegrityError:
        # `unique_together = ('husband', 'wife')` -- a second create for the
        # same pair hits the DB constraint; report it, never a raw 500.
        raise PersonValidationError(DUPLICATE_MARRIAGE_DETAIL)


def apply_marriage_update(marriage, data):
    """Only `order`, `status` and `note` ever change; partners are immutable
    (delete and recreate to fix a wrong partner).
    """
    if 'order' in data:
        validate_marriage_order_unique(
            orders_for_husband(marriage.husband_id, exclude_marriage_id=marriage.id), data['order'],
        )
    with transaction.atomic():
        for field in _MUTABLE_FIELDS:
            if field in data:
                setattr(marriage, field, data[field])
        marriage.save()
    return marriage


def apply_marriage_delete(marriage):
    marriage.delete()
