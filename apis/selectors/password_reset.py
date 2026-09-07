"""Queries and writes for `PasswordResetCode`.

ORM lives here rather than in `services/`, which must stay pure
(`docs/code-standards.md` -> Layering).
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from apis.models import PasswordResetCode
from apis.services.otp import hash_code

# Codes older than this are deleted opportunistically on the next request from
# the same user, so the table stays bounded without a cron job. Well past any
# TTL, so it can never remove a code still in play.
STALE_CODE_AGE = timedelta(days=1)

# Per-USER cap on reset requests. This is the limit an attacker cannot escape
# by rotating source addresses -- the per-IP throttle scope can be, and
# `NUM_PROXIES=0` makes those buckets weak to begin with (djangopj/settings.py).
MAX_REQUESTS_PER_HOUR = 3


def user_for_email(email):
    """The ACTIVE account `email` identifies, or None.

    `is_active` is part of the filter, not an afterthought: a deactivated or
    banned account must not be recoverable through mailbox possession, which
    would make this endpoint an account-reactivation bypass.

    Registration stores `username = email` lower-cased, but rows created by
    the admin or by the old social login may not be normalised -- hence
    `iexact` on BOTH columns rather than a plain lookup on `username`.

    `.first()` and not `.get()`: `auth_user.email` carries NO unique
    constraint in stock Django, so two rows can genuinely share an address and
    `.get()` would raise `MultipleObjectsReturned` -> 500 on an
    unauthenticated endpoint. Oldest row wins, deterministically.
    """
    return (
        User.objects
        .filter(Q(username__iexact=email) | Q(email__iexact=email), is_active=True)
        .order_by('id')
        .first()
    )


def recent_request_count(user):
    """How many codes `user` has been issued in the last hour."""
    return PasswordResetCode.objects.filter(
        user=user, created_at__gt=timezone.now() - timedelta(hours=1),
    ).count()


def issue_code(user, code):
    """Store `code` for `user` and invalidate every earlier unused code.

    Superseding is what stops a user who clicks "resend" three times from
    leaving three live codes on the account. Without it an attacker requests N
    codes and gets N x MAX_ATTEMPTS guesses against a WIDENING set of targets,
    so each request would make the account easier to break into rather than
    harder.
    """
    ttl = settings.PASSWORD_RESET_CODE_TTL_SECONDS
    now = timezone.now()
    PasswordResetCode.objects.filter(user=user, created_at__lt=now - STALE_CODE_AGE).delete()
    PasswordResetCode.objects.filter(user=user, used_at__isnull=True).update(used_at=now)
    return PasswordResetCode.objects.create(
        user=user,
        code_hash=hash_code(code, user.pk),
        expires_at=now + timedelta(seconds=ttl),
    )


def active_code_for(user):
    """The newest code that is unused and unexpired, or None.

    Attempt exhaustion is NOT filtered here -- a burnt-out code must keep
    being found so the caller can answer "too many attempts" instead of
    silently behaving as if no code was ever requested.
    """
    return (
        PasswordResetCode.objects
        .filter(user=user, used_at__isnull=True, expires_at__gt=timezone.now())
        .order_by('-id')
        .first()
    )
