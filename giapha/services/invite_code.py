"""Invite-code generation and expiry/exhaustion checks.

Pure Python -- no ORM, no `request` -- so this stays testable with
`SimpleTestCase` (no database needed).
"""

import secrets

CODE_LENGTH = 8
# 0/O and 1/I dropped: they are visually ambiguous when a code is read aloud
# or hand-copied.
ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def generate_code(length=CODE_LENGTH):
    """A random invite code drawn from `ALPHABET` via `secrets.choice`."""
    return ''.join(secrets.choice(ALPHABET) for _ in range(length))


def is_expired(invite, now):
    """True if `invite.expires_at` is set and has passed as of `now`."""
    return invite.expires_at is not None and invite.expires_at <= now


def is_exhausted(invite):
    """True if `invite.max_uses` is capped (>0) and that cap is reached.

    `max_uses == 0` means unlimited uses.
    """
    return invite.max_uses > 0 and invite.used_count >= invite.max_uses
