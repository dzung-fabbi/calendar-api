"""Invite reads added with member-issued invites (plan 260919 phase 1).

The original owner-only readers (`invites_of`, `get_invite_by_id`,
`get_invite_for_update`) stay in `selectors/clan.py`.
"""

from django.db.models import F, Q

from giapha.models import ClanInvite, ClanMember, Person


def invites_created_by(clan_id, user_id):
    """A member's own invites, newest first -- what a non-approver may list."""
    return ClanInvite.objects.filter(clan_id=clan_id, created_by_id=user_id).order_by('-created_at')


def open_invite_count(clan_id, user_id, now):
    """Invites by `user_id` in `clan_id` that are still pending, or active and
    neither expired nor used up -- the anti-spam cap counts these.
    """
    usable = Q(status='active') & (Q(expires_at__isnull=True) | Q(expires_at__gt=now)) & (
        Q(max_uses=0) | Q(used_count__lt=F('max_uses'))
    )
    return (
        ClanInvite.objects.filter(clan_id=clan_id, created_by_id=user_id)
        .filter(Q(status='pending_approval') | usable)
        .count()
    )


def get_invite_for_review(clan_id, invite_id):
    """Lock one invite of `clan_id` for approve/reject. Caller must be in `atomic()`."""
    return ClanInvite.objects.select_for_update().filter(clan_id=clan_id, id=invite_id).first()


def lock_person_for_claim(clan_id, person_id):
    """Lock a live Person of `clan_id` so two redemptions of invites naming the
    same node serialize on it. Caller must be in `atomic()`.
    """
    return Person.objects.select_for_update().filter(clan_id=clan_id, id=person_id, is_deleted=False).first()


def person_is_claimed(person_id):
    """Any member (verified or not) already bound to `person_id`."""
    return ClanMember.objects.filter(person_id=person_id).exists()
