"""Sexagenary (can chi) day naming and lunar-month calendar helpers."""

import datetime as dt

from lunarcalendar import Converter, Lunar, Solar

CAN = ["Giáp", "Ất", "Bính", "Đinh", "Mậu", "Kỷ", "Canh", "Tân", "Nhâm", "Quý"]
CHI = ["Tý", "Sửu", "Dần", "Mão", "Thìn", "Tỵ", "Ngọ", "Mùi", "Thân", "Dậu", "Tuất", "Hợi"]

# 1984-01-31 is a Giáp Tý day, the start of a 60-day cycle. (An older comment
# here claimed 1984-02-02; that date is Bính Dần. The constant was right and
# the comment was wrong.)
GIAP_TY_EPOCH = dt.date(1984, 1, 31)


def can_chi_for_date(solar_date):
    """Return the can-chi name of a solar date, e.g. 'Giáp Tý'."""
    days = (solar_date - GIAP_TY_EPOCH).days
    return "{} {}".format(CAN[days % 10], CHI[days % 12])


def solar_to_date(solar_obj):
    """Convert a lunarcalendar Solar object to a stdlib date."""
    return dt.date(solar_obj.year, solar_obj.month, solar_obj.day)


def lunar_month_solar_range(year, month):
    """Solar (first_day, last_day) covering one lunar month.

    A lunar month is 29 or 30 days, so those are the only lengths probed. (The
    original probed 31 and 28 as well; 31 can never succeed and 28 is never
    reached.) Deliberately *not* derived from the next month's first day: that
    would swallow an intercalary leap month into the range.
    """
    year, month = int(year), int(month)
    first = solar_to_date(Converter.Lunar2Solar(Lunar(year, month, 1)))

    for length in (30, 29):
        try:
            last = solar_to_date(Converter.Lunar2Solar(Lunar(year, month, length)))
        except Exception:
            continue
        return first, last

    raise ValueError('No valid last day for lunar month {}/{}'.format(month, year))


def can_chi_index_for_lunar_month(year, month):
    """Map every can-chi name in a lunar month to its solar date.

    Built once per request so callers can look a day up in O(1) instead of
    re-walking the month for every row they need to resolve.
    """
    first, last = lunar_month_solar_range(year, month)
    index = {}
    current = first
    while current <= last:
        # A 29/30-day lunar month cannot repeat a can-chi, but keep the first
        # occurrence if it ever did, matching the original scan order.
        index.setdefault(can_chi_for_date(current).upper(), current)
        current += dt.timedelta(days=1)
    return index


def solar_date_to_lunar_string(solar_date):
    """Render a solar date as the 'lunar_year-month-day' string the API returns."""
    lunar = Converter.Solar2Lunar(
        Solar(solar_date.year, solar_date.month, solar_date.day)
    )
    return '{}-{}-{}'.format(lunar.year, lunar.month, lunar.day)
