"""giapha's own API exceptions.

Mirrors `apis/exceptions.py` in shape, but giapha must not import from `apis`
(package boundary), so it keeps a small copy of its own.
"""

from rest_framework import status
from rest_framework.exceptions import APIException


class BadRequestException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Yêu cầu không hợp lệ.'
    default_code = 'error'


class ServiceUnavailableException(APIException):
    """Raised by the photo endpoints when S3/R2 is not configured (phase 8).

    Deliberately 503, not 500 -- this is an operator/config fault ("nobody
    set the storage credentials on this host yet"), retryable once someone
    fixes the config, and semantically the right client-facing code for
    that: a client (or an on-call engineer) reading a 503 has the correct
    mental model, "try again later / go fix the deploy", where a 500 would
    read as "the code is broken". This does NOT mean it reads any
    differently in server-side monitoring than a 500 would -- Django's
    `log_response` logs every 5xx response at `ERROR`, DRF `APIException`s
    included, so this still shows up as an ERROR-level log line same as any
    other exception. The 503 choice is about client contract, not about
    suppressing an operator alert; if that log volume ever becomes a
    problem, that's a monitoring/alerting-threshold decision to make
    separately, not a reason to change the status code. Scoped to the photo
    endpoints only; the rest of the API keeps working with no storage
    configured at all.
    """
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Chưa cấu hình lưu trữ ảnh; vui lòng thử lại sau.'
    default_code = 'error'
