"""Bulk revocation of a user's OAuth2 tokens.

Called after a password change or reset so that a session opened with the old
password cannot outlive it -- the point of changing a password after a
compromise is to evict whoever else is holding one.

VERIFIED AGAINST django-oauth-toolkit 2.2.0 (`oauth2_provider/models.py`):

  * `RefreshToken.access_token` is a `OneToOneField(..., on_delete=SET_NULL)`,
    NOT a cascade. Deleting access tokens first therefore leaves the refresh
    tokens alive with a null pointer -- still rows, still the user's. Refresh
    tokens must go FIRST, or there is a window in which one can be swapped for
    a brand-new access token.
  * `RefreshToken.revoke()` marks a `revoked` timestamp instead of deleting,
    and `Meta.unique_together = ('token', 'revoked')` makes revoking in bulk
    that way awkward. Deleting is both simpler and more complete.
  * There is no `token_family` in this version, so there is no third table to
    clean up. OIDC `IDToken` rows are not touched either: the project sets no
    `OAUTH2_PROVIDER` block and issues none. Add them here if OIDC is enabled.
"""

from django.db import transaction
from oauth2_provider.models import get_access_token_model, get_refresh_token_model


def revoke_all_tokens(user):
    """Delete every OAuth2 token belonging to `user`, refresh tokens first.

    Returns `(refresh_deleted, access_deleted)` for logging and tests.

    The caller is responsible for wrapping this and the `set_password` in one
    `transaction.atomic()`, so a failure cannot leave the password changed and
    the old sessions alive.
    """
    refresh_deleted, _ = get_refresh_token_model().objects.filter(user=user).delete()
    access_deleted, _ = get_access_token_model().objects.filter(user=user).delete()
    return refresh_deleted, access_deleted


def set_password_and_revoke_tokens(user, new_password):
    """Change `user`'s password and evict every existing session, atomically.

    Shared by the reset and the change endpoints, which must behave identically
    here. Revocation is the whole point of the operation in the compromise
    case: were the two not in one transaction, a failure could leave the
    password changed while the attacker's tokens stayed live.
    """
    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=['password'])
        revoke_all_tokens(user)
