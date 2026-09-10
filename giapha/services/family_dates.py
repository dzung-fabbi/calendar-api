"""Date/time formatting for the personal family API (spec §3.1).

Wire formats are the app's, not ISO: dates are `"DD-MM-YYYY"`, times are a
separate `"HH:mm"` string, timestamps are epoch milliseconds. Pure functions,
no ORM.

`derive_solar_death` implements spec §2.4: the death date is entered in the
LUNAR calendar and the solar date is computed at write time only when day,
month AND year are known -- the same lunar day falls on a different solar
date every year, so a missing year means no solar date at all.
"""

import datetime as dt
import re

from giapha.services.vn_lunar import MAX_YEAR, MIN_YEAR, lunar_to_solar

DATE_FORMAT = '%d-%m-%Y'
TIME_PATTERN = r'^([01]\d|2[0-3]):[0-5]\d$'
TIME_RE = re.compile(TIME_PATTERN)


def format_date(value):
    """`date` -> `"DD-MM-YYYY"`, or `None` for `None`."""
    return value.strftime(DATE_FORMAT) if value is not None else None


def epoch_ms(value):
    """Aware `datetime` -> integer epoch milliseconds (what the app stores in
    `createdAt`/`updatedAt`)."""
    if value is None:
        return None
    return int(value.timestamp() * 1000)


def has_lunar_death(day, month):
    """Spec §7: a giỗ mark needs day 1–30 and month 1–12; the year may be
    missing."""
    return day is not None and month is not None and 1 <= day <= 30 and 1 <= month <= 12


def derive_solar_death(day, month, year, leap):
    """Solar `date` for a complete lunar death date, else `None`.

    Tries the leap flag the client sent first; if that flag does not match
    the year (`vn_lunar` raises), falls back to the regular month rather than
    failing the write -- `lunarLeap` is display-only per the spec and must
    never block saving a person.
    """
    if not has_lunar_death(day, month) or year is None:
        return None
    if not (MIN_YEAR <= year <= MAX_YEAR):
        return None
    for is_leap in ((1, 0) if leap else (0,)):
        try:
            dd, mm, yy = lunar_to_solar(day, month, year, is_leap)
        except ValueError:
            continue
        try:
            return dt.date(yy, mm, dd)
        except ValueError:
            return None
    return None
