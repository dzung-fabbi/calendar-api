"""Bulk eviction of a user's sessions after a password change or reset.

The point of changing a password after a compromise is to evict whoever else
is holding a session. Two token kinds, two mechanisms:

  * REFRESH tokens are rows (`apis.RefreshToken`) and are DELETED here.
  * ACCESS tokens are stateless JWTs and cannot be deleted. They die through
    the `pwd` claim (`apis/services/jwt_tokens.password_fingerprint`): it is
    derived from `user.password`, which `set_password()` rewrites with a fresh
    salt, so every token minted before the change stops matching at once.

That second mechanism is why `revoke_all_tokens` is only ever correct when it
runs in the SAME transaction as the `set_password()` -- on its own it leaves
every access token alive for the rest of its lifetime.
"""

from django.db import transaction

from apis.models import RefreshToken


def revoke_all_tokens(user):
    """Delete every refresh token belonging to `user`. Returns the count."""
    return RefreshToken.objects.filter(user=user).delete()[0]


def set_password_and_revoke_tokens(user, new_password):
    """Change `user`'s password and evict every existing session, atomically.

    Shared by the reset and the change endpoints, which must behave identically
    here. Were the two writes not in one transaction, a failure could leave the
    password changed while an attacker's refresh token stayed live.
    """
    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=['password'])
        revoke_all_tokens(user)
