"""Query-parameter validation.

The read views used to wrap their whole body in `except Exception: raise
BadRequestException()`, which turned a missing parameter, a malformed number
and a genuine server fault into the same anonymous 400. Validating up front
lets a bad request say what was wrong and lets a real bug surface (and be
logged) as a 500.
"""

import json

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apis.exceptions import BadRequestException


class InvalidParam(BadRequestException):
    """A 400 that names the offending parameter."""

    def __init__(self, name, reason):
        super().__init__("Tham số '{}' không hợp lệ: {}".format(name, reason))


def required(request, name):
    value = request.GET.get(name)
    if value is None or value == '':
        raise InvalidParam(name, 'bắt buộc')
    return value


def required_int(request, name):
    value = required(request, name)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise InvalidParam(name, 'phải là số nguyên')


def required_json_list(request, name):
    """Parse a JSON array parameter, e.g. CalendarAPIView's `data`."""
    raw = required(request, name)
    try:
        value = json.loads(raw)
    except ValueError:
        raise InvalidParam(name, 'phải là JSON hợp lệ')
    if not isinstance(value, list):
        raise InvalidParam(name, 'phải là một mảng JSON')
    return value


def required_datetime(request, name):
    """Parse a datetime parameter, returning an aware value.

    `USE_TZ` is on, so handing the ORM the raw naive string made Django warn
    and guess the timezone on every request.
    """
    raw = required(request, name)
    value = parse_datetime(raw)
    if value is None:
        raise InvalidParam(name, 'phải có dạng YYYY-MM-DD HH:MM:SS')
    if timezone.is_naive(value):
        value = timezone.make_aware(value)
    return value
