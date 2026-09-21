"""Best-effort FCM pushes for clan collaboration events (invites, bindings,
change requests).

Sits beside `permissions.py` rather than in `services/` because it needs a
DB read (device tokens) AND the network: `services/` stays ORM-free,
`selectors/` stays network-free, and both views and management commands call
this module.

`fcm.send_multicast` never raises on network trouble (per-token results) and
returns `{}` when FCM is not configured, so a push can never turn a
successful write into an error. Sends run on `transaction.on_commit`: a push
must not announce something a later rollback undid.
"""

from django.db import transaction

from giapha.selectors.gio_follow import active_tokens_for
from giapha.services import fcm


def _send_now(user_ids, title, body, data):
    tokens_by_user = active_tokens_for(user_ids)
    tokens = [token for tokens in tokens_by_user.values() for token in tokens]
    if tokens:
        fcm.send_multicast(tokens, title, body, data)


def push_to_users(user_ids, title, body, data=None):
    """Queue one notification to every active device of `user_ids`."""
    user_ids = sorted({user_id for user_id in user_ids if user_id is not None})
    if not user_ids:
        return
    transaction.on_commit(lambda: _send_now(user_ids, title, body, data or {}))
