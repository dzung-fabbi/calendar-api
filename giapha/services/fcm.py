"""Firebase Cloud Messaging, HTTP v1. Network -- but still no ORM.

The legacy `Authorization: key=<server key>` endpoint was switched off by
Google in June 2024, so v1 (service account + OAuth2 bearer token) is the
only option. `google-auth` + `requests` rather than `firebase-admin`: we need
exactly one endpoint and `requests` is already a dependency.

LAYERING: this module reports, it never writes. A token that comes back
`UNREGISTERED`/`INVALID_ARGUMENT` is dead and should be deactivated, but
flipping `DeviceToken.is_active` is the management command's job -- keeping
the ORM out of `services/` is what `docs/code-standards.md` -> Layering asks
for, and it also keeps this module testable without a database.

The credentials/OAuth half lives in `fcm_auth.py` -- this module is the
send path only (it was over the 200-line limit as one file).

MISSING CREDENTIALS ARE NOT AN ERROR: `send_multicast` returns `{}` and logs
a warning instead of raising, so the nightly cron exits 0 on a host that was
never given a service account rather than mailing a stack trace every day.

`{}` MEANS "NOT CONFIGURED", NOTHING ELSE. A transient failure while minting
the OAuth token (DNS, a Google 5xx) is not a configuration problem and must
not read as one: it comes back as `{token: ERROR_NETWORK}` per token, exactly
like a transient failure on the send itself. Collapsing the two once made the
caller abandon every remaining recipient of a run -- and print "Firebase is
not configured" in a run where a push had already gone out.
"""

import logging

import requests

from giapha.services.fcm_auth import FcmTransientError, access_token, credentials_info

logger = logging.getLogger(__name__)

FCM_ENDPOINT = 'https://fcm.googleapis.com/v1/projects/{}/messages:send'
REQUEST_TIMEOUT_SECONDS = 10

RESULT_OK = 'ok'
ERROR_UNREGISTERED = 'UNREGISTERED'
ERROR_INVALID_ARGUMENT = 'INVALID_ARGUMENT'
ERROR_NETWORK = 'network_error'
# The caller deactivates the `DeviceToken` behind any result in this tuple:
# the app was uninstalled, or the token string is malformed. Every other
# failure (5xx, timeout) is transient and the token stays active.
DEAD_TOKEN_RESULTS = (ERROR_UNREGISTERED, ERROR_INVALID_ARGUMENT)


def _redact(device_token):
    """Device tokens are credentials: log a prefix and a length, never the
    whole string (phase 6 -> Security Considerations)."""
    return '{}...({} chars)'.format(device_token[:6], len(device_token))


def _classify(response, device_token):
    """HTTP error response -> the string reported for that device token.

    v1 puts the actionable code in `error.details[].errorCode`
    (`UNREGISTERED` for an uninstalled app), with `error.status` as the
    coarser fallback. Both dead-token codes are surfaced verbatim so the
    caller can match them against `DEAD_TOKEN_RESULTS`.
    """
    try:
        error = (response.json() or {}).get('error') or {}
    except ValueError:
        error = {}

    code = ''
    for detail in error.get('details') or ():
        if isinstance(detail, dict) and detail.get('errorCode'):
            code = detail['errorCode']
            break
    code = code or error.get('status') or ''

    if code in DEAD_TOKEN_RESULTS:
        return code
    logger.warning(
        'FCM rejected %s: HTTP %s %s', _redact(device_token), response.status_code, code,
    )
    return 'HTTP {}{}'.format(response.status_code, ' ' + code if code else '')


def _send_one(url, headers, device_token, message_body):
    message = dict(message_body, token=device_token)
    try:
        response = requests.post(
            url, headers=headers, json={'message': message}, timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        # One unreachable send must never abort the rest of the batch.
        logger.warning('FCM send failed for %s: %s', _redact(device_token), exc)
        return ERROR_NETWORK
    if response.status_code == 200:
        return RESULT_OK
    return _classify(response, device_token)


def send_multicast(tokens, title, body, data=None):
    """Push one notification to many device tokens.

    Returns `{token: RESULT_OK | error string}` -- one entry per token, and
    `{}` ONLY when there is nothing to attempt with: no tokens, or no usable
    service account. An empty result is the caller's "FCM is not configured"
    signal; it is never an exception, and it never stands for a transient
    failure (see the module docstring).

    v1 has no true multicast, so this is a loop of single sends sharing one
    OAuth token; a token's failure lands on its own entry and never aborts
    the rest of the batch.
    """
    tokens = list(tokens)
    if not tokens:
        return {}

    try:
        info = credentials_info()
    except FcmTransientError as exc:
        # A credentials file that cannot be read right now (rotation, a flaky
        # mount) is weather, not configuration -- same treatment as a failed
        # token mint below. Returning `{}` here would tell the caller "FCM is
        # off" and throw away the rest of the run.
        logger.warning(
            'Temporary failure reading FCM credentials (%s); %s notification(s) '
            'need a retry.', exc, len(tokens),
        )
        return dict((token, ERROR_NETWORK) for token in tokens)
    if info is None:
        logger.warning('FCM credentials not configured; %s notification(s) skipped.', len(tokens))
        return {}
    project_id = info.get('project_id')
    if not project_id:
        logger.warning('Service account JSON has no project_id; FCM disabled.')
        return {}

    try:
        bearer = access_token(info)
    except FcmTransientError as exc:
        # Reported per token, exactly like a failed send: the caller records a
        # retriable failure for these recipients and keeps going, instead of
        # reading `{}` as "Firebase is off" and abandoning the run.
        logger.warning(
            'Temporary failure obtaining an FCM access token (%s); %s notification(s) '
            'need a retry.', exc, len(tokens),
        )
        return dict((token, ERROR_NETWORK) for token in tokens)
    if bearer is None:
        return {}

    url = FCM_ENDPOINT.format(project_id)
    headers = {
        'Authorization': 'Bearer {}'.format(bearer),
        'Content-Type': 'application/json; UTF-8',
    }
    # v1 rejects non-string values inside `data`; coerce, don't earn a 400.
    message_body = {
        'notification': {'title': title, 'body': body},
        'data': {str(key): str(value) for key, value in (data or {}).items()},
    }
    return {token: _send_one(url, headers, token, message_body) for token in tokens}
