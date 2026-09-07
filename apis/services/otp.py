"""Generation and verification of the 6-digit password-reset code.

Pure -- no ORM, no `request` (`docs/code-standards.md` -> Layering), so
`test_services.py` can exercise it on `SimpleTestCase`.

WHY HMAC-SHA256 AND NOT `django.contrib.auth.hashers.make_password`:

  * A 6-digit code has 10**6 possible values. A deliberately slow password
    hash is designed to make guessing a *high-entropy* secret expensive; over
    a keyspace this small it buys nothing -- anyone holding the table can
    enumerate every value regardless of the hash's cost factor. What actually
    protects the stored code is that the HMAC key (`SECRET_KEY`) lives
    OUTSIDE the database, so a dump of the table alone yields nothing.
  * `djangopj/settings_test.py` swaps in `MD5PasswordHasher` for speed, so
    `make_password` would be verified under a hasher production never uses.

Comparison goes through `hmac.compare_digest`: a plain `==` on the hex digest
leaks, through its timing, how many leading characters matched.
"""

import hmac
import secrets
from hashlib import sha256

from django.conf import settings

CODE_LENGTH = 6
DIGITS = '0123456789' 


def generate_code():
    """A cryptographically random `CODE_LENGTH`-digit string.

    `secrets.choice` per digit, mirroring `giapha/services/invite_code.py` --
    uniform over all 10**CODE_LENGTH values, leading zeros included, and with
    no chance of the `str(randbelow(10**6))` variant's silent keyspace loss.

    `secrets`, never `random`: the latter is a Mersenne Twister seeded from
    the clock, and its next output is derivable from a handful of prior
    samples -- exactly the attack a reset code has to survive.
    """
    return ''.join(secrets.choice(DIGITS) for _ in range(CODE_LENGTH))


def hash_code(code, user_id):
    """Hex HMAC-SHA256 of `code`, bound to `user_id`, under `SECRET_KEY`.

    64 chars, matching `PasswordResetCode.code_hash`'s max_length.

    `user_id` is inside the signed message so that the same six digits issued
    to two people produce two different hashes. Nothing today looks a code up
    by its hash, so this is defence in depth -- but it means a stored hash can
    never be replayed against another account even if such a lookup is added.
    """
    message = '{}:{}'.format(user_id, code).encode('utf-8')
    return hmac.new(settings.SECRET_KEY.encode('utf-8'), message, sha256).hexdigest()


def codes_match(code_hash, code, user_id):
    """Constant-time comparison of a candidate `code` against a stored hash."""
    if not code_hash or not code:
        return False
    return hmac.compare_digest(code_hash, hash_code(code, user_id))
