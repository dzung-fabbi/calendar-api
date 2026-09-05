"""DB-facing queries for Marriage."""

from giapha.models import Marriage


def get_marriage_or_none(clan_id, marriage_id):
    return (
        Marriage.objects.filter(
            id=marriage_id, husband__clan_id=clan_id,
            husband__is_deleted=False, wife__is_deleted=False,
        )
        .select_related('husband', 'wife')
        .first()
    )


def marriages_of(clan_id):
    """Marriages of `clan_id` with both partners still live -- a soft-deleted
    partner's name must not keep leaking through a different endpoint than
    the one that filtered it out.
    """
    return (
        Marriage.objects.filter(
            husband__clan_id=clan_id, husband__is_deleted=False, wife__is_deleted=False,
        )
        .select_related('husband', 'wife')
        .order_by('husband_id', 'order')
    )


def orders_for_husband(husband_id, exclude_marriage_id=None):
    """`[(marriage_id, order), ...]` for every marriage of `husband_id`,
    optionally excluding one marriage (used when updating its own order).
    """
    queryset = Marriage.objects.filter(husband_id=husband_id)
    if exclude_marriage_id is not None:
        queryset = queryset.exclude(id=exclude_marriage_id)
    return list(queryset.values_list('id', 'order'))


def next_order_for_husband(husband_id):
    """`max(order) + 1` for `husband_id`'s existing marriages, or 1 if none."""
    orders = Marriage.objects.filter(husband_id=husband_id).values_list('order', flat=True)
    return (max(orders) if orders else 0) + 1
