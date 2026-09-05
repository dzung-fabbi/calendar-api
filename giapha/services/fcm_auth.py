"""FCM credentials and OAuth2 access tokens -- the auth half of `fcm.py`.

Split out of `services/fcm.py` to keep both files under the 200-line rule
(`CLAUDE.md` -> Modularization); the seam is natural, one module answers "who
are we" and the other "send this".

TWO KINDS OF FAILURE, DELIBERATELY NOT THE SAME VALUE:

* `None` / no credentials  -> CONFIGURATION. FCM is switched off on this
  host; the caller stops cleanly and exits 0.
* `FcmTransientError`      -> WEATHER. DNS, a Google 5xx, a timeout while
  minting. The caller must report a retriable per-token failure and carry on
  with the rest of the batch.

Collapsing them into one sentinel is what once let a single OAuth blip
abandon a whole nightly run while logging "Firebase is not configured".

No ORM here either (`docs/code-standards.md` -> Layering).
"""

import json
import logging
import os
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

FCM_SCOPE = 'https://www.googleapis.com/auth/firebase.messaging'
# Google mints 1-hour tokens; expire ours early so a send never starts with a
# token that dies mid-flight.
TOKEN_TTL_SECONDS = 3000

# Keyed on the service account it was minted for: a rotation, or a second
# project, must not be served the previous project's bearer token for the
# rest of the TTL.
_token_cache = {'key': None, 'value': None, 'expires_at': 0.0}


class FcmTransientError(Exception):
    """Minting an access token failed for a reason that may not recur.

    Distinct from "no usable credentials" (which stays `None`): the caller
    must keep working through the rest of its batch and retry later, not
    conclude that FCM is switched off on this host.
    """


def _setting(name):
    """`settings.<name>` if the project defines it, else the process env.

    Everything else in this codebase reads configuration through
    `django.conf.settings`; reading `os.environ` alone meant a deploy that set
    the value in `settings.py` silently got no FCM, and that `override_settings`
    could not reach this module from a test.
    """
    value = getattr(settings, name, None)
    if value:
        return value
    return os.environ.get(name)


def credentials_info():
    """Service account dict from `FIREBASE_CREDENTIALS_JSON` (raw content) or
    `FIREBASE_CREDENTIALS_PATH` (file).

    `None` means CONFIGURATION: unset, or present but malformed. The caller
    should stop -- no amount of retrying fixes a bad service account.

    Raises `FcmTransientError` when the path is set but cannot be READ right
    now (rotated out from under a running job, a transient mount failure).
    That is weather, not configuration: the file is expected to be there and
    probably will be on the next run, so the caller must carry on with the
    rest of the batch rather than abandon it and announce "FCM is off".
    Collapsing unreadable into `None` was the same mistake `_mint_token`
    already guards against, one function to the left.
    """
    raw = _setting('FIREBASE_CREDENTIALS_JSON')
    if raw:
        try:
            return json.loads(raw)
        except ValueError:
            logger.warning('FIREBASE_CREDENTIALS_JSON is not valid JSON; FCM disabled.')
            return None

    path = _setting('FIREBASE_CREDENTIALS_PATH')
    if not path:
        return None
    try:
        with open(path, 'r') as handle:
            content = handle.read()
    except (IOError, OSError) as exc:
        # NOT `return None`: see the docstring. `IOError` is an alias of
        # `OSError` on py3, kept for grep-ability against the 3.9 pin.
        logger.warning(
            'Cannot read FIREBASE_CREDENTIALS_PATH=%s right now (%s); treating as transient.',
            path, exc,
        )
        raise FcmTransientError(str(exc))
    try:
        return json.loads(content)
    except ValueError:
        logger.warning('FIREBASE_CREDENTIALS_PATH=%s is not valid JSON; FCM disabled.', path)
        return None


def _mint_token(info):
    """One fresh OAuth2 bearer token for `info`.

    `None` when the credentials themselves are unusable (package missing,
    unparseable service account) -- a CONFIGURATION fault, the caller should
    stop. Raises `FcmTransientError` when the network or Google refused to
    mint one right now -- a TRANSIENT fault, the caller should carry on with
    the rest of the batch and retry later.

    `google-auth` is imported lazily on purpose: importing
    `giapha.services.fcm` must stay free of hard dependencies, so a host (or
    a test image built before the requirements bump) without the package
    fails only on the send path, never at import time.
    """
    try:
        from google.auth.exceptions import GoogleAuthError
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError:
        logger.warning('google-auth is not installed; FCM disabled.')
        return None

    try:
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=[FCM_SCOPE],
        )
    except ValueError as exc:
        # A service account dict the library cannot even parse will not parse
        # on the next run either: configuration, not weather.
        logger.warning('Service account JSON is not usable (%s); FCM disabled.', exc)
        return None

    try:
        credentials.refresh(Request())
    except (GoogleAuthError, requests.RequestException) as exc:
        raise FcmTransientError(str(exc))
    return credentials.token


def _cache_key(info):
    """Identity of the service account -- never its secret material."""
    return (info.get('project_id'), info.get('client_email'), info.get('private_key_id'))


def access_token(info):
    """`_mint_token` behind a TTL cache -- one token per run, not one per
    device: a nightly batch of a few hundred pushes would otherwise open a
    few hundred OAuth handshakes. Keyed on the service account, so rotating
    credentials cannot be served the previous project's token.

    Propagates `FcmTransientError`, and caches nothing in that case.
    """
    now = time.time()
    key = _cache_key(info)
    if (_token_cache['value'] is not None and _token_cache['key'] == key
            and now < _token_cache['expires_at']):
        return _token_cache['value']

    token = _mint_token(info)
    _token_cache['key'] = key
    _token_cache['value'] = token
    _token_cache['expires_at'] = now + TOKEN_TTL_SECONDS if token else 0.0
    return token
