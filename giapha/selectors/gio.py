"""DB-facing query for the `lich-gio` endpoint.

One query, whatever the clan size. Deliberately `.values()` on a short field
list rather than model instances: the view only needs the lunar death fields
plus enough identity to render a row, and instantiating 5.000 `Person`
objects to read six attributes off each is the difference between a fast
endpoint and a timeout.

Intended to be served by `giapha_person_clan_gio_idx`, the `(clan,
death_lunar_month, death_lunar_day)` index added in phase 1. Not verified
with EXPLAIN: the predicate is `clan_id = ? AND is_deleted = 0 AND ... IS NOT
NULL`, and `IS NOT NULL` on the 2nd/3rd index columns is weakly selective, so
MySQL may well prefer the plain `clan_id` FK index. Either plan is fine at
the 5.000-person ceiling; worth an EXPLAIN before raising that ceiling.
"""

from giapha.models import Person

# `death_lunar_leap` is deliberately NOT fetched: a giỗ is always observed in
# the regular month (see `services.gio`), so the flag has no bearing on the
# result and selecting it would invite a future reader to "use" it.
GIO_ROW_FIELDS = (
    'id', 'ho_ten', 'thuy_hieu', 'generation',
    'death_lunar_day', 'death_lunar_month',
)


def deceased_with_lunar_death(clan_id, max_persons):
    """`(rows, truncated)` for non-deleted persons of `clan_id` who have a
    usable lunar death date.

    Both day and month must be present: a month alone cannot produce a giỗ
    date, and a row half-filled that way would otherwise be silently dropped
    further down instead of never entering the sweep.

    Bounded at the DB with `LIMIT max_persons + 1` -- one extra row is all
    `truncated` needs -- rather than materialising an unbounded clan into
    memory. Same guard, same reason, as `selectors.tree.tree_payload`: each
    person can yield two rows in the response, so an unbounded clan at the
    5.000 ceiling is ~10.000 items.
    """
    rows = list(
        Person.objects.filter(
            clan_id=clan_id,
            is_deleted=False,
            death_lunar_day__isnull=False,
            death_lunar_month__isnull=False,
        )
        .values(*GIO_ROW_FIELDS)
        .order_by('id')[:max_persons + 1]
    )
    truncated = len(rows) > max_persons
    return rows[:max_persons], truncated
