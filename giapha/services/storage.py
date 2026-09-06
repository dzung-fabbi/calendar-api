"""S3/R2 object storage for `Person.photo_key` -- presigned upload/download.

WHY PRESIGNED URLS: pushing photo bytes through Django ties up a gunicorn
sync worker for as long as the upload takes; a handful of concurrent 5MB
uploads is enough to starve every other request. Presigning pushes the
bandwidth to S3/R2 directly -- Django only ever sees a key string, never a
byte of image data (phase-08 spec).

`boto3` is used for BOTH real S3 and Cloudflare R2: R2 implements the S3 API,
so `endpoint_url` alone is what changes between them, not the SDK.

TWO KINDS OF FAILURE, DELIBERATELY NOT THE SAME VALUE (same convention as
`services/fcm_auth.py`):

* `is_configured() -> False` / `StorageNotConfigured` -- CONFIGURATION. No
  bucket/credentials on this host. The photo endpoints answer 503 and the
  rest of the API keeps working (see `views/photo.py`).
* Any `botocore` exception out of `head`/`delete`/the presign calls -- WEATHER.
  Network, wrong credentials, S3 down. Callers let it propagate to a 500;
  there is no "retry the rest of a batch" concept on a single-request path.

HONESTY ABOUT THE SIZE LIMIT: `presign_put` uses `generate_presigned_url`
with `ClientMethod='put_object'`. That call has NO `Conditions` parameter --
`content-length-range` is only enforceable through `generate_presigned_post`
(a browser form upload, not a `PUT`). Since the client here issues a plain
`PUT` to the returned URL (phase-08 spec's flow), a presigned PUT genuinely
CANNOT enforce the 5MB cap up front: a client that ignores its own declared
`size` can still push a larger object. The cap is therefore enforced for
real only at the confirm step, via `head()` reading back `ContentLength`
after the fact (`views/photo.py`'s confirm endpoint). Do not read `max_bytes`
below as an enforced limit -- it is accepted for interface/documentation
parity with the phase-08 spec and is not applied by this function.

No ORM here (`docs/code-standards.md` -> Layering).
"""

import logging
import os

import boto3
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)

PRESIGN_PUT_TTL_SECONDS = 300
PRESIGN_GET_TTL_SECONDS = 3600

# Built once, lazily, keyed on the resolved config tuple so a settings change
# (a real deploy, or `override_settings` in a test) is picked up without
# needing a process restart -- rebuilding a boto3 client is cheap enough that
# comparing the config tuple on every call is not worth avoiding.
_client_cache = {'client': None, 'config_key': None}


class StorageNotConfigured(Exception):
    """Raised by `_client()` when required S3/R2 settings are missing.

    Callers that only need a yes/no answer (the person serializer's
    `photo_url`, the photo endpoints deciding whether to answer 503) should
    check `is_configured()` first rather than catching this.
    """


def _setting(name):
    """`settings.<name>` if set, else the process env -- same pattern as
    `services/fcm_auth._setting`, for the same reason: everything else reads
    configuration through `django.conf.settings`, and only that path is
    reachable from `override_settings` in tests.
    """
    value = getattr(settings, name, None)
    if value:
        return value
    return os.environ.get(name)


def _config():
    """`(endpoint_url, bucket, access_key, secret_key, region)` or `None` if
    the required trio (bucket + both credentials) is missing. `endpoint_url`
    and `region` are optional -- real S3 needs neither (region defaults to
    the client's own default resolution), R2 needs both.
    """
    bucket = _setting('S3_BUCKET')
    access_key = _setting('S3_ACCESS_KEY_ID')
    secret_key = _setting('S3_SECRET_ACCESS_KEY')
    if not (bucket and access_key and secret_key):
        return None
    return (
        _setting('S3_ENDPOINT_URL') or None,
        bucket,
        access_key,
        secret_key,
        _setting('S3_REGION') or None,
    )


def is_configured():
    """`True` once bucket + credentials are set. Used by callers that must
    degrade gracefully (503, or a `null` `photo_url`) instead of raising.
    """
    return _config() is not None


def reset_client_cache():
    """Test-only escape hatch. Drop the cached client so the next call
    rebuilds one -- needed when a test patches `boto3.client` itself (a
    `mock.Mock()`) rather than changing the config tuple that would
    otherwise trigger a rebuild on its own. Production code never calls
    this; config changing mid-process outside of tests is not a real
    scenario.
    """
    _client_cache['client'] = None
    _client_cache['config_key'] = None


def _client():
    config = _config()
    if config is None:
        raise StorageNotConfigured(
            'Thiếu cấu hình lưu trữ ảnh (S3_BUCKET/S3_ACCESS_KEY_ID/S3_SECRET_ACCESS_KEY).'
        )
    if _client_cache['config_key'] != config:
        endpoint_url, bucket, access_key, secret_key, region = config
        _client_cache['client'] = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        _client_cache['config_key'] = config
    return _client_cache['client']


def _bucket():
    return _setting('S3_BUCKET')


def presign_put(key, content_type):
    """Presigned `PUT` URL for `key`, valid `PRESIGN_PUT_TTL_SECONDS`.

    Takes no size parameter (L1: a `max_bytes` argument used to be accepted
    here and immediately discarded) -- see the module docstring's "HONESTY
    ABOUT THE SIZE LIMIT" section for why a presigned `PUT` cannot enforce
    one. The real size check happens in `head()`, called from the confirm
    endpoint after upload.
    """
    client = _client()
    return client.generate_presigned_url(
        'put_object',
        Params={'Bucket': _bucket(), 'Key': key, 'ContentType': content_type},
        ExpiresIn=PRESIGN_PUT_TTL_SECONDS,
    )


def presign_get(key, expires_in=PRESIGN_GET_TTL_SECONDS):
    """Presigned `GET` URL for `key`. Default TTL is 1 hour (phase-08 spec):
    long enough to be cacheable client-side, short enough that a leaked link
    does not stay valid forever.
    """
    client = _client()
    return client.generate_presigned_url(
        'get_object', Params={'Bucket': _bucket(), 'Key': key}, ExpiresIn=expires_in,
    )


def head(key):
    """`{'content_length': int, 'content_type': str_or_None}` for `key`, or
    `None` if the object does not exist (S3 answers 404/`NoSuchKey`/`NotFound`
    depending on provider) -- the confirm view treats `None` as "client named
    a key that was never actually uploaded" and answers 400.

    ALSO `None` on 403/`AccessDenied` (M3): a missing key legitimately comes
    back as 403 rather than 404 when the credential lacks `s3:ListBucket` --
    the default for an object-scoped R2 token, and a common least-privilege
    S3 setup too. Without this, that (very normal) configuration makes every
    "the client named a key that was never uploaded" case 500 instead of
    400, and the whole point of `views/photo.py`'s `OBJECT_NOT_FOUND_DETAIL`
    check becomes unreachable in production. This mapping is DELIBERATELY
    ambiguous, though -- a 403 here could ALSO mean a genuine credential
    misconfiguration unrelated to the key (wrong bucket policy, revoked
    key, ...), not just a missing object, and silently treating every 403
    as "not found" would hide that from an operator. Hence the
    `logger.warning` below: the confirm request still gets its correct 400,
    but the ambiguity itself stays visible in logs rather than disappearing.
    See `docs/deployment-guide.md` for how to grant `s3:ListBucket` and get
    an unambiguous 404 instead.

    Any other `ClientError` (network, wrong credentials, provider outage) is
    a genuine fault and propagates -- there is nothing sensible to degrade to
    on a single confirm request.
    """
    client = _client()
    try:
        response = client.head_object(Bucket=_bucket(), Key=key)
    except ClientError as exc:
        error_code = exc.response.get('Error', {}).get('Code')
        if error_code in ('403', 'AccessDenied'):
            logger.warning(
                'head_object 403 cho key=%s -- có thể là ảnh chưa tồn tại, '
                'hoặc thiếu quyền s3:ListBucket trên bucket (xem '
                'docs/deployment-guide.md). Đang xử lý như "không tìm thấy".',
                key,
            )
            return None
        if error_code in ('404', 'NoSuchKey', 'NotFound'):
            return None
        raise
    return {
        'content_length': response['ContentLength'],
        'content_type': response.get('ContentType'),
    }


def delete(key):
    """Delete `key`. `delete_object` is idempotent on S3/R2 -- deleting an
    already-gone key is not an error -- so this is a thin passthrough; the
    caller (confirm/delete views) is responsible for the swallow+log
    decision documented in the phase-08 spec (a failed delete must leave
    orphaned storage, never a lost photo or a broken response).
    """
    client = _client()
    client.delete_object(Bucket=_bucket(), Key=key)
