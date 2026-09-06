"""`Clan.public_slug` generation for the phase-9 share link.

Pure Python, no ORM -- `secrets.token_urlsafe` needs no database, so this
stays testable with `SimpleTestCase`. Uniqueness/retry-on-collision lives
where the DB write happens (`views.clan.ClanPublicLinkAPIView.post`),
mirroring `services.invite_code.generate_code` + its call site.
"""

import secrets

# 16 random bytes -> `secrets.token_urlsafe` emits ~4/3 as many base64url
# characters, i.e. 22 -- long enough that guessing a live slug is
# infeasible, and comfortably under `Clan.public_slug`'s `max_length=32`.
SLUG_NBYTES = 16


def generate_public_slug():
    """22 URL-safe characters, cryptographically random."""
    return secrets.token_urlsafe(SLUG_NBYTES)
