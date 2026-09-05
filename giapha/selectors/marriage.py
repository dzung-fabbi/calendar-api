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


def clan_spouse_pairs(clan_id):
    """`[(husband_id, wife_id, status, order), ...]` for the marriages in
    `clan_id` that still create a kinship term. One query, scalars only --
    the consumer is `services.kinship`, which is pure and works on ids.

    `ly_hon` IS EXCLUDED, `goa` IS NOT. A widow keeps being her late
    husband's family's thím; a divorced wife stops being one. That is the
    everyday Vietnamese usage, and the choice is visible here rather than
    buried in the term table.

    `status` AND `order` TRAVEL WITH THE PAIR because keeping `goa` is only
    half an answer: a widow who remarried has TWO live rows, and the service
    has to prefer the current husband over the late one. Dropping the two
    columns here left it ranking by autoincrement id, which routed the wife
    of a younger brother through the dead elder one and called his elder
    brother `em`. Ranking rule: `services.kinship_marriage_rows`.

    Both partners must be non-deleted, same rule as `marriages_of`: a
    soft-deleted person must not re-enter through a different endpoint.
    """
    return list(
        Marriage.objects.filter(
            husband__clan_id=clan_id,
            husband__is_deleted=False,
            wife__is_deleted=False,
        )
        .exclude(status='ly_hon')
        .values_list('husband_id', 'wife_id', 'status', 'order')
    )
