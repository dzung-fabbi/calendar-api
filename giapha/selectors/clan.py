"""DB-facing queries for Clan / ClanMember / ClanInvite.

Every read here filters out soft-deleted clans, so nothing above this layer
needs to remember `is_deleted=False` itself.
"""

from giapha.models import Clan, ClanInvite, ClanMember


def get_clan_or_none(clan_id):
    return Clan.objects.filter(id=clan_id, is_deleted=False).first()


def get_clan_by_public_slug(slug):
    """Resolves the phase-9 public share link. Only a clan that is BOTH not
    soft-deleted AND currently `visibility == 'public_link'` matches -- a
    slug left over from a revoked link, or a clan an owner has since made
    private again, must behave exactly like an unknown slug (`None` here,
    a 404 above), never a different response that would confirm the clan
    still exists.

    CASE-SENSITIVE by construction, not by luck: MySQL's `utf8_unicode_ci`
    collation makes the `WHERE public_slug = slug` comparison itself
    case-INSENSITIVE, so the query can return a clan whose real slug only
    matches `slug` up to case. `services.public_slug.generate_public_slug`
    promises ~2^115 bits of entropy against guessing -- a promise that is
    quietly false if an upper-cased mangling of a slug (e.g. a copy-paste
    through a case-folding client, or a stale link reissued after a revoke)
    still resolves. The exact-match check below is Python-side and
    case-sensitive regardless of collation; it costs a second string
    comparison per lookup, never a second query.
    """
    clan = Clan.objects.filter(public_slug=slug, visibility='public_link', is_deleted=False).first()
    if clan is None or clan.public_slug != slug:
        return None
    return clan


def clans_for_user(user):
    """Clans `user` belongs to, most recently joined first."""
    return (
        Clan.objects
        .filter(is_deleted=False, members__user=user)
        .distinct()
        .order_by('-created_at')
    )


def clan_role_for(user, clan_id):
    """Role of `user` in `clan_id`, or None if not a member (or clan gone).

    None deliberately covers both "never joined" and "clan soft-deleted" --
    callers (permissions.py) turn None into a 404, never a 403, so neither
    case leaks whether the clan exists.
    """
    if not clan_id:
        return None
    member = (
        ClanMember.objects
        .filter(clan_id=clan_id, clan__is_deleted=False, user=user)
        .only('role')
        .first()
    )
    return member.role if member else None


def roles_for_clans(user, clan_ids):
    """{clan_id: role} for `user` across `clan_ids`, in one query.

    Used by the "my clans" list so per-row owner checks (public_slug
    visibility) don't cost one query per row.
    """
    rows = ClanMember.objects.filter(clan_id__in=list(clan_ids), user=user).values_list('clan_id', 'role')
    return dict(rows)


def members_of(clan_id):
    return (
        ClanMember.objects
        .filter(clan_id=clan_id)
        .select_related('user')
        .order_by('joined_at')
    )


def member_by_user_id(clan_id, user_id):
    return ClanMember.objects.filter(clan_id=clan_id, user_id=user_id).select_related('user').first()


def owner_count(clan_id):
    return ClanMember.objects.filter(clan_id=clan_id, role='owner').count()


def get_invite_for_update(code):
    """Lock the invite row for a redemption. Caller must be in `transaction.atomic()`."""
    return (
        ClanInvite.objects
        .select_for_update()
        .filter(code=code, clan__is_deleted=False)
        .first()
    )


def invites_of(clan_id):
    """Every invite ever issued for `clan_id`, newest first -- the owner-only
    listing that gives a leaked code somewhere to be found and revoked from.
    """
    return ClanInvite.objects.filter(clan_id=clan_id).order_by('-created_at')


def get_invite_by_id(clan_id, invite_id):
    return ClanInvite.objects.filter(clan_id=clan_id, id=invite_id).first()
