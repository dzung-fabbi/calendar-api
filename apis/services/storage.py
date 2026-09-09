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

`boto3` serves BOTH real S3 and Cloudflare R2 -- only `endpoint_url` differs.
Settings are the same five `S3_*` that `giapha` reads: no second bucket, no
second credential.

TWO KINDS OF FAILURE, DELIBERATELY NOT THE SAME VALUE:

* `is_configured() -> False` / `StorageNotConfigured` -- CONFIGURATION. No
  bucket/credentials on this host. The file endpoints answer 503 and the rest
  of the API keeps working (see `views/file_upload.py`).
* Any `botocore` exception out of `head`/the presign calls -- WEATHER. Network,
  wrong credentials, S3 down. Callers let it propagate to a 500.

HONESTY ABOUT THE SIZE LIMIT: a presigned `PUT` genuinely CANNOT enforce one --
`generate_presigned_url(ClientMethod='put_object')` has no `Conditions`
parameter (`content-length-range` only exists on `generate_presigned_post`, a
form upload). The cap is enforced for real only at confirm, via `head()`
reading back the real `ContentLength`.

No ORM here (`docs/code-standards.md` -> Layering).
"""

import logging
import os

import boto3
from botocore.config import Config
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
    the required trio (bucket + both credentials) is missing.

    `S3_ENDPOINT_URL` stays empty for real S3 (R2 requires it). When it is
    empty and `S3_REGION` is set, the regional endpoint is derived HERE rather
    than left to botocore -- see the comment below. Both empty is still valid.
    """
    bucket = _setting('S3_BUCKET')
    access_key = _setting('S3_ACCESS_KEY_ID')
    secret_key = _setting('S3_SECRET_ACCESS_KEY')
    if not (bucket and access_key and secret_key):
        return None
    region = _setting('S3_REGION') or None
    endpoint_url = _setting('S3_ENDPOINT_URL') or None
    if endpoint_url is None and region:
        # REAL S3, REGION KNOWN: address the region explicitly instead of
        # letting botocore fall back to the global `s3.amazonaws.com`. This
        # pinned botocore (1.31) resolves virtual-host addressing to that
        # global host even with `region_name` set, and the global host answers
        # HTTP 307 -> regional for a bucket whose DNS has not propagated yet
        # (up to 24h after creation). A 307 kills a presigned PUT outright:
        # most HTTP clients will not replay the request body on a redirect.
        endpoint_url = 'https://s3.{}.amazonaws.com'.format(region)
    return (endpoint_url, bucket, access_key, secret_key, region)


def is_configured():
    """`True` once bucket + credentials are set -- callers that must degrade
    gracefully (503) check this instead of catching."""
    return _config() is not None


def reset_client_cache():
    """Test-only. Drop the cached client so the next call rebuilds one --
    needed when a test patches `boto3.client` itself rather than changing the
    config tuple. Production never calls this."""
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
            # SIGNATURE VERSION IS NOT OPTIONAL. Left to botocore's own
            # default, this pinned botocore (1.31) presigns S3 URLs with
            # SigV2 against the legacy global host -- which every region
            # created after 2014 rejects outright, and R2 requires SigV4 too.
            # s3v4 also makes botocore resolve the regional endpoint from
            # `region_name`, removing the 307 described in `_config()`.
            config=Config(signature_version='s3v4'),
        )
        _client_cache['config_key'] = config
    return _client_cache['client']


def _bucket():
    return _setting('S3_BUCKET')


def presign_put(key, content_type):
    """Presigned `PUT` URL for `key`, valid `PRESIGN_PUT_TTL_SECONDS`. Takes no
    size parameter -- see the module docstring for why a presigned `PUT` cannot
    enforce one; `head()` at confirm time is where the cap is real.
    """
    client = _client()
    return client.generate_presigned_url(
        'put_object',
        Params={'Bucket': _bucket(), 'Key': key, 'ContentType': content_type},
        ExpiresIn=PRESIGN_PUT_TTL_SECONDS,
    )


def presign_get(key, expires_in=PRESIGN_GET_TTL_SECONDS):
    """Presigned `GET` URL for `key`. 1 hour by default: cacheable client-side,
    short enough that a leaked link expires. The bucket stays private, so this
    is the only way a caller ever reads an object back.
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

    ALSO `None` on 403/`AccessDenied`: a missing key comes back as 403, not
    404, when the credential lacks `s3:ListBucket` -- the default for an
    object-scoped R2 token, which would otherwise turn every "key was never
    uploaded" case into a 500. The mapping is DELIBERATELY ambiguous (a 403
    can also mean a real credential fault), hence the `logger.warning`: the
    request still gets its 400, the ambiguity stays in the logs. Any other
    `ClientError` propagates.
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
