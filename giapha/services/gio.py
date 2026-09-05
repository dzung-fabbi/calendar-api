"""Ngày giỗ (kỵ nhật) -- when a death anniversary falls on the solar calendar.

Pure functions over `vn_lunar`; no ORM, no request cycle, so the whole module
is testable with `SimpleTestCase`.

THE ANNIVERSARY IS LUNAR, ALWAYS
--------------------------------
A giỗ recurs on the lunar day/month of the death, so its solar date moves
every year. The solar death date is a reference only -- never compute a giỗ
from it.

THE THREE CUSTOMARY RULES
-------------------------
| Situation                                   | Observed on                  |
|---------------------------------------------|------------------------------|
| Died day 30, this year's month has only 29  | day 29 (`adjusted=True`)     |
| Died in a leap month                        | the regular month, same number|
| Died in a regular month that leaps this year| the regular month            |

The last two collapse into one implementation detail: a giỗ is *always* looked
up in the regular (non-intercalary) month, so `is_leap` is hard-coded to 0 in
the single call to `lunar_to_solar` below. A family that also observes the
leap-month occurrence is a real but rare custom, out of scope here.
"""

import datetime as dt
from collections import namedtuple

from giapha.services.vn_lunar import (
    MAX_YEAR,
    MIN_YEAR,
    lunar_month_length,
    lunar_to_solar,
    solar_to_lunar,
)

# Vietnam is UTC+7 year-round (no DST). `settings.TIME_ZONE` is UTC, so
# `timezone.localdate()` would roll over 7 hours late and report yesterday's
# `days_until` for most of the Vietnamese evening.
VN_TZ = dt.timezone(dt.timedelta(hours=7))

# `day` is the lunar day actually observed -- 29 when a day-30 giỗ was pulled
# back, otherwise the recorded death day.
GioOccurrence = namedtuple('GioOccurrence', 'solar_date day month lunar_year adjusted')


def today_vn():
    """Today's date in Vietnam, independent of the server's timezone."""
    return dt.datetime.now(VN_TZ).date()


def gio_occurrence(death_day, death_month, lunar_year):
    """The single giỗ of one person in one lunar year.

    Returns a `GioOccurrence`, or `None` when `lunar_year` falls outside the
    range `vn_lunar` supports -- callers sweep a range of years and should
    skip what cannot be computed rather than fail the whole response.
    """
    if not (MIN_YEAR - 1 <= lunar_year <= MAX_YEAR):
        return None
    # `person_rules.validate_lunar_death_valid` enforces these bounds on the
    # API write path, but a row can also arrive via Django admin, a fixture,
    # a bulk import, or predate that validation. Out-of-range values do NOT
    # blow up downstream -- month 13 resolves to an offset past the year end
    # and day 31 runs into the next month -- they produce a well-formed date
    # in the WRONG month. Skipping is the only safe answer: this module's
    # whole premise is that no giỗ beats a wrong giỗ.
    if not (1 <= death_month <= 12 and 1 <= death_day <= 30):
        return None

    day = death_day
    adjusted = False
    # Rule 1: a day-30 giỗ has no date at all in a 29-day (thiếu) month.
    if day == 30 and lunar_month_length(death_month, lunar_year) == 29:
        day = 29
        adjusted = True

    dd, mm, yy = lunar_to_solar(day, death_month, lunar_year, 0)
    return GioOccurrence(dt.date(yy, mm, dd), day, death_month, lunar_year, adjusted)


def lunar_years_covering(start, end):
    """Every lunar year whose months can produce a giỗ inside `start..end`.

    A lunar year lags the solar one by up to ~7 weeks, so a solar window can
    touch the tail of the lunar year before it and the head of the one after.
    Both edges are widened by one year and the caller filters precisely; the
    cost is at most two throwaway conversions per person.
    """
    first = solar_to_lunar(start.day, start.month, start.year)[2]
    last = solar_to_lunar(end.day, end.month, end.year)[2]
    lo = max(first - 1, MIN_YEAR - 1)
    hi = min(last + 1, MAX_YEAR)
    return range(lo, hi + 1)


def gio_occurrences_in_range(death_day, death_month, start, end, lunar_years=None):
    """Every giỗ of one person landing in the solar window `start..end`.

    A list, not a single date: one solar year can hold two giỗ of the same
    person (a month-12 giỗ can fall in January and again in December), and a
    window shorter than a lunar year can hold none.

    `lunar_years` lets a caller computing many people over one window hoist
    `lunar_years_covering()` out of the loop.
    """
    if lunar_years is None:
        lunar_years = lunar_years_covering(start, end)

    found = []
    for lunar_year in lunar_years:
        occurrence = gio_occurrence(death_day, death_month, lunar_year)
        if occurrence is not None and start <= occurrence.solar_date <= end:
            found.append(occurrence)
    return found
