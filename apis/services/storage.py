"""S3/R2 object storage for the generic file-upload endpoints -- presigned PUT/GET.

DELIBERATE TWIN OF `giapha/services/storage.py`. `docs/code-standards.md` ->
Decoupling forbids `apis/` importing `giapha/` and states duplicate code is
preferable to a cross-app dependency, so this is a copy, not an import.
**A behavioural fix here needs the same fix there, and vice versa.** The two
differ in exactly one way: this module has no `delete()`, because `apis/` has
no endpoint that removes an object.

WHY PRESIGNED URLS: pushing file bytes through Django ties up a gunicorn sync
worker for as long as the upload takes; a handful of concurrent 5MB uploads is
enough to starve every other request. Presigning pushes the bandwidth to S3/R2
directly -- Django only ever sees a key string, never a byte of file data.

`boto3` is used for BOTH real S3 and Cloudflare R2: R2 implements the S3 API,
so `endpoint_url` alone is what changes between them, not the SDK. Settings are
the same `S3_*` five that `giapha` reads (`djangopj/settings.py`); there is no
second bucket and no second credential to configure.

TWO KINDS OF FAILURE, DELIBERATELY NOT THE SAME VALUE:

* `is_configured() -> False` / `StorageNotConfigured` -- CONFIGURATION. No
  bucket/credentials on this host. The file endpoints answer 503 and the rest
  of the API keeps working (see `views/file_upload.py`).
* Any `botocore` exception out of `head`/the presign calls -- WEATHER. Network,
  wrong credentials, S3 down. Callers let it propagate to a 500.

HONESTY ABOUT THE SIZE LIMIT: a presigned `PUT` genuinely CANNOT enforce one.
`generate_presigned_url(ClientMethod='put_object')` has no `Conditions`
parameter -- `content-length-range` only exists on `generate_presigned_post` (a
browser form upload, not a `PUT`). A client that ignores its own declared
`size` can still push a larger object. The cap is enforced for real only at the
confirm step, via `head()` reading back `ContentLength` after the fact.

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

    Callers that only need a yes/no answer (the file endpoints deciding
    whether to answer 503) should check `is_configured()` first rather than
    catching this.
    """


def _setting(name):
    """`settings.<name>` if set, else the process env -- only the settings path
    is reachable from `override_settings` in tests.
    """
    value = getattr(settings, name, None)
    if value:
        return value
    return os.environ.get(name)


def _config():
    """`(endpoint_url, bucket, access_key, secret_key, region)` or `None` if
    the required trio (bucket + both credentials) is missing. `endpoint_url`
    and `region` are optional -- real S3 needs neither (region defaults to the
    client's own default resolution), R2 needs both.
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
    degrade gracefully (503) instead of raising.
    """
    return _config() is not None


def reset_client_cache():
    """Test-only escape hatch. Drop the cached client so the next call rebuilds
    one -- needed when a test patches `boto3.client` itself (a `mock.Mock()`)
    rather than changing the config tuple. Production code never calls this.
    """
    _client_cache['client'] = None
    _client_cache['config_key'] = None


def _client():
    config = _config()
    if config is None:
        raise StorageNotConfigured(
            'Thiếu cấu hình lưu trữ tệp (S3_BUCKET/S3_ACCESS_KEY_ID/S3_SECRET_ACCESS_KEY).'
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

    Takes no size parameter -- see the module docstring's "HONESTY ABOUT THE
    SIZE LIMIT" for why a presigned `PUT` cannot enforce one. The real size
    check happens in `head()`, called from the confirm endpoint after upload.
    """
    client = _client()
    return client.generate_presigned_url(
        'put_object',
        Params={'Bucket': _bucket(), 'Key': key, 'ContentType': content_type},
        ExpiresIn=PRESIGN_PUT_TTL_SECONDS,
    )


def presign_get(key, expires_in=PRESIGN_GET_TTL_SECONDS):
    """Presigned `GET` URL for `key`. Default TTL is 1 hour: long enough to be
    cacheable client-side, short enough that a leaked link does not stay valid
    forever. The bucket itself stays private -- this is the only way a caller
    ever reads an object back.
    """
    client = _client()
    return client.generate_presigned_url(
        'get_object', Params={'Bucket': _bucket(), 'Key': key}, ExpiresIn=expires_in,
    )


def head(key):
    """`{'content_length': int, 'content_type': str_or_None}` for `key`, or
    `None` if the object does not exist (S3 answers 404/`NoSuchKey`/`NotFound`
    depending on provider) -- the confirm view treats `None` as "client named a
    key that was never actually uploaded" and answers 400.

    ALSO `None` on 403/`AccessDenied`: a missing key comes back as 403 rather
    than 404 when the credential lacks `s3:ListBucket` -- the default for an
    object-scoped R2 token. Without this, that normal setup turns every
    "key was never uploaded" case into a 500. The mapping is DELIBERATELY
    ambiguous (a 403 can also mean a real credential fault), hence the
    `logger.warning`: the request still gets its 400, the ambiguity stays in
    the logs. Any other `ClientError` is a genuine fault and propagates.
    """
    client = _client()
    try:
        response = client.head_object(Bucket=_bucket(), Key=key)
    except ClientError as exc:
        error_code = exc.response.get('Error', {}).get('Code')
        if error_code in ('403', 'AccessDenied'):
            logger.warning(
                'head_object 403 cho key=%s -- có thể là tệp chưa tồn tại, hoặc '
                'thiếu quyền s3:ListBucket trên bucket (xem docs/deployment-guide.md). '
                'Đang xử lý như "không tìm thấy".',
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
