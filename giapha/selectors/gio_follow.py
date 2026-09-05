"""DB-facing queries for the giỗ-reminder recipient resolution.

Every function here returns a plain dict keyed by id, never model instances:
the consumers are `services.gio_follow` (pure, no ORM) and the daily reminder
command, and both work on id sets. Loading model objects to read two columns
off each would be the difference between a 5-query job and an N+1 one.

The whole point of this module is that resolving "who gets reminded" costs a
FIXED number of queries per clan, no matter how many people are followed --
see `views/gio_follow.py` for the endpoint that has an `assertNumQueries`
pinning that contract.
"""

from giapha.models import ClanMember, DeviceToken, GioFollow, GioNotificationLog


def binding_map(clan_id):
    """`{user_id: person_id}` for members of `clan_id` who bound themselves.

    Members with `person=NULL` are absent, not mapped to `None`: an unbound
    member has no direct line and must receive nothing by default. Silence is
    the honest answer; guessing is worse.
    """
    return dict(
        ClanMember.objects
        .filter(clan_id=clan_id, person__isnull=False)
        .values_list('user_id', 'person_id')
    )


def overrides_for_clan(clan_id):
    """`{(user_id, person_id): enabled}` for every override in `clan_id`
    that belongs to a CURRENT member of that clan.

    Keyed by the pair because `services.gio_follow.followers_by_person`
    resolves one user at a time and needs O(1) lookup per candidate person.

    THE MEMBERSHIP JOIN IS A PRIVACY GUARD, NOT A TIDINESS ONE: removing a
    member deletes their `ClanMember` row (and with it the binding), but
    leaves their `GioFollow` rows standing. Without the join an ex-member
    keeps receiving pushes carrying a deceased person's name from a clan
    every endpoint now answers 404 for. `ClanMember.user` has no
    `related_name`, hence the default `user__clanmember__` reverse path; it
    is a JOIN, so this stays ONE query.

    Non-destructive on purpose -- the rows survive so a member who leaves and
    rejoins gets their preferences back rather than a silently reset list.
    """
    rows = (
        GioFollow.objects
        .filter(person__clan_id=clan_id, user__clanmember__clan_id=clan_id)
        .values_list('user_id', 'person_id', 'enabled')
    )
    return {(user_id, person_id): enabled for user_id, person_id, enabled in rows}


def follow_rows_for_user(clan_id, user_id):
    """`{person_id: enabled}` -- one user's overrides inside `clan_id`.

    The single-user narrowing of `overrides_for_clan`, for the endpoint,
    which must never read another member's preferences.
    """
    return dict(
        GioFollow.objects
        .filter(person__clan_id=clan_id, user_id=user_id)
        .values_list('person_id', 'enabled')
    )


def active_tokens_for(user_ids):
    """`{user_id: [token, ...]}` for the still-active devices of `user_ids`.

    One query for the whole recipient set. Empty in, empty out -- an
    `IN ()` against no ids is a query worth not making.
    """
    user_ids = list(user_ids)
    if not user_ids:
        return {}
    tokens = {}
    rows = (
        DeviceToken.objects
        .filter(user_id__in=user_ids, is_active=True)
        .values_list('user_id', 'token')
    )
    for user_id, token in rows:
        tokens.setdefault(user_id, []).append(token)
    return tokens


def member_binding(clan_id, user_id):
    """The caller's `ClanMember` row with its bound `Person` already joined.

    `selectors.clan.member_by_user_id` joins `user`, which this caller does
    not need, and not `person`, which it does -- hence a second, narrower
    reader here rather than a second query on top of that one.
    """
    return (
        ClanMember.objects
        .filter(clan_id=clan_id, user_id=user_id)
        .select_related('person')
        .first()
    )


def person_claimed_by_other(person_id, user_id):
    """True when a *different* user has already bound themselves to `person_id`.

    Checked before writing so the OneToOne collision surfaces as a 400 with a
    Vietnamese message instead of an `IntegrityError` 500. The write itself
    still guards against the race -- this only makes the common case civil.
    """
    return (
        ClanMember.objects
        .filter(person_id=person_id)
        .exclude(user_id=user_id)
        .exists()
    )


def notified_pairs(person_ids, solar_dates):
    """`{(person_id, user_id, solar_date)}` recorded as `status='sent'` in
    `GioNotificationLog` for these persons and giỗ dates -- one query.

    `unique_together` on the log is the real de-duplication guarantee, but
    reading the set up front is what makes a second run of the same day send
    NOTHING, rather than send and only then fail to record it.

    ONLY `sent` ROWS BLOCK. A `failed` row must NOT: a person is due on
    exactly ONE calendar day a year (`target = today + N` advances with
    `today`), so a pair blocked by a failed attempt would never be retried at
    all -- a 07:00 DNS blip would silently cost that ancestor their giỗ
    notice for a year. Re-running the command after the outage now retries
    exactly the pairs that failed, and never the ones that succeeded.
    """
    person_ids = list(person_ids)
    solar_dates = list(solar_dates)
    if not person_ids or not solar_dates:
        return set()
    return set(
        GioNotificationLog.objects
        .filter(person_id__in=person_ids, solar_date__in=solar_dates, status='sent')
        .values_list('person_id', 'user_id', 'solar_date')
    )
