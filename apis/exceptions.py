from rest_framework import status
from rest_framework.exceptions import APIException


class BadRequestException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Bad request'
    default_code = 'error'


class ServiceUnavailableException(APIException):
    """Raised by the file-upload endpoints when S3/R2 is not configured.

    Deliberately 503, not 500 -- this is an operator/config fault ("nobody set
    the storage credentials on this host yet"), retryable once someone fixes
    the config. A client (or an on-call engineer) reading a 503 has the correct
    mental model, "try again later / go fix the deploy", where a 500 would read
    as "the code is broken". Note it does NOT read differently in server-side
    monitoring: Django's `log_response` logs every 5xx at ERROR, DRF
    `APIException`s included. The choice is about client contract, not about
    suppressing an alert. Scoped to the file endpoints; the rest of the API
    keeps working with no storage configured at all.
    """
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = 'Chưa cấu hình lưu trữ tệp; vui lòng thử lại sau.'
    default_code = 'error'
