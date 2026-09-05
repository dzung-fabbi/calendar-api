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
