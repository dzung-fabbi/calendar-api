"""Vietnamese lunar calendar (âm lịch Việt Nam), UTC+7.

Port of Hồ Ngọc Đức's `amlich-hnd.js`, the de-facto reference implementation
for the Vietnamese lunar calendar. Astronomical formulae are Jean Meeus,
*Astronomical Algorithms* (mean new moon + corrections, apparent solar
longitude). Algorithm spec and sourced test vectors:
`plans/reports/researcher-260905-1610-vn-lunar-ho-ngoc-duc-algorithm.md`.

WHY NOT `lunarcalendar` (already a dependency, used by `apis/`)
---------------------------------------------------------------
`lunarcalendar` computes the CHINESE lunar calendar at UTC+8. Vietnam uses
UTC+7, and a new moon falling near midnight UTC lands on different calendar
days in the two zones -- which can shift a whole lunar month, and with it
every giỗ (death anniversary) in it. The documented VN/CN Tết divergences
since Vietnam adopted UTC+7 are 1968, 1969, 1985 and 2007, and this module
reproduces exactly those:

    1968  VN 29/01  TQ 30/01   (one day)
    1985  VN 21/01  TQ 20/02   (a FULL MONTH -- different leap placement)
    2007  VN 17/02  TQ 18/02   (one day)

Getting a giỗ date wrong is the one failure this module exists to prevent, so
`apis/` keeps `lunarcalendar` (its almanac golden snapshots depend on it) and
`giapha/` uses this module. That divergence is deliberate; see
`docs/system-architecture.md`.

WHERE THE TIMEZONE IS APPLIED
-----------------------------
Exactly one place: `get_new_moon_day()`'s `+ tz / 24` term. Every month
boundary in the module flows through it, so there is a single point to audit
and a single point that can break.

FLOOR, NOT TRUNCATE
-------------------
The reference uses JavaScript `Math.floor`. Python's `int()` truncates toward
zero, which differs for negative operands -- and operands DO go negative here
for dates before 1900 (`k` is counted from the 1900-01-31 new moon) and inside
`sun_longitude()`'s normalisation. Every integer conversion below therefore
uses `math.floor`.
"""

import math
from functools import lru_cache

# UTC+7. A module constant, not a per-call default sprinkled across signatures:
# a caller must never be able to half-switch the module to another timezone.
TIMEZONE = 7

# Julian Day Number of the first new moon after 1900-01-31, and the mean
# synodic month. Together they index new moons: k = 0 is that first new moon.
NEW_MOON_EPOCH = 2415021.076998695
SYNODIC_MONTH = 29.530588853

# Outside this range the underlying polynomials drift past a full day and a
# wrong giỗ date is worse than no answer. Astronomically 1900-2100 is exact
# and the outer bands are ±1 day. Callers must surface this as HTTP 400,
# never a silent result.
#
# CAVEAT -- `TIMEZONE` is a constant, but Vietnam's offset was not.
# Vietnam observed UTC+8 for 1943-01-01..1945-09-14, 1947-04-01..1955-06-30
# and 1960-01-01..1967-12-31. Converting a SOLAR date inside those windows at
# tz=7 disagrees with the official calendar of the day on ~230 dates, around
# 8 month boundaries -- e.g. 1965-02-01 reads as mùng 1 Tết here but was
# 30/12 of the previous lunar year in Vietnam at the time. The giỗ endpoint
# never converts historical solar dates (it sweeps forward from modern window
# bounds), so this is latent, not live -- but a future "convert my ancestor's
# solar death date" feature needs a `tz_for_date()` lookup table first, and
# ancestors born before 1968 are exactly this app's population.
MIN_YEAR = 1800
MAX_YEAR = 2199

_DEG = math.pi / 180


def _check_year(yy):
    if not (MIN_YEAR <= yy <= MAX_YEAR):
        raise ValueError(
            'Năm {} nằm ngoài khoảng hỗ trợ [{}, {}].'.format(yy, MIN_YEAR, MAX_YEAR)
        )


def _check_lunar_year(ly):
    """One year wider than `_check_year` on the low side.

    A lunar year runs ~7 weeks behind the solar one, so solar `MIN_YEAR`
    January is lunar month 11 or 12 of `MIN_YEAR - 1`. Rejecting that would
    make `solar_to_lunar` -> `lunar_to_solar` asymmetric at the boundary.
    """
    if not (MIN_YEAR - 1 <= ly <= MAX_YEAR):
        raise ValueError(
            'Năm âm lịch {} nằm ngoài khoảng hỗ trợ [{}, {}].'.format(
                ly, MIN_YEAR - 1, MAX_YEAR
            )
        )


def jd_from_date(dd, mm, yy):
    """Gregorian date -> Julian Day Number.

    Gregorian only: the reference falls back to the Julian calendar below
    JDN 2299161 (1582-10-05), which `MIN_YEAR = 1800` makes unreachable.
    """
    a = math.floor((14 - mm) / 12)
    y = yy + 4800 - a
    m = mm + 12 * a - 3
    return (
        dd
        + math.floor((153 * m + 2) / 5)
        + 365 * y
        + math.floor(y / 4)
        - math.floor(y / 100)
        + math.floor(y / 400)
        - 32045
    )


def jd_to_date(jd):
    """Julian Day Number -> `(dd, mm, yy)` Gregorian."""
    a = jd + 32044
    b = math.floor((4 * a + 3) / 146097)
    c = a - math.floor((b * 146097) / 4)
    d = math.floor((4 * c + 3) / 1461)
    e = c - math.floor((1461 * d) / 4)
    m = math.floor((5 * e + 2) / 153)

    day = e - math.floor((153 * m + 2) / 5) + 1
    month = m + 3 - 12 * math.floor(m / 10)
    year = b * 100 + d - 4800 + math.floor(m / 10)
    return day, month, year


def new_moon(k):
    """Julian day (fractional, UTC) of the k-th new moon since 1900-01-31.

    Meeus' mean new moon plus the periodic corrections for solar and lunar
    anomaly and the Moon's argument of latitude, minus ΔT.
    """
    t = k / 1236.85  # Julian centuries from 1900-01-00.5
    t2 = t * t
    t3 = t2 * t

    jd1 = 2415020.75933 + 29.53058868 * k + 0.0001178 * t2 - 0.000000155 * t3
    jd1 += 0.00033 * math.sin((166.56 + 132.87 * t - 0.009173 * t2) * _DEG)

    # Sun's mean anomaly, Moon's mean anomaly, Moon's argument of latitude.
    m = 359.2242 + 29.10535608 * k - 0.0000333 * t2 - 0.00000347 * t3
    mpr = 306.0253 + 385.81691806 * k + 0.0107306 * t2 + 0.00001236 * t3
    f = 21.2964 + 390.67050646 * k - 0.0016528 * t2 - 0.00000239 * t3

    # Written one signed term per line, in the reference's order, so each can
    # be diffed against `amlich-hnd.js` by eye. Do not "tidy" into fewer lines.
    c1 = (0.1734 - 0.000393 * t) * math.sin(_DEG * m)
    c1 += 0.0021 * math.sin(_DEG * 2 * m)
    c1 += -0.4068 * math.sin(_DEG * mpr)
    c1 += 0.0161 * math.sin(_DEG * 2 * mpr)
    c1 += -0.0004 * math.sin(_DEG * 3 * mpr)
    c1 += 0.0104 * math.sin(_DEG * 2 * f)
    c1 += -0.0051 * math.sin(_DEG * (m + mpr))
    c1 += -0.0074 * math.sin(_DEG * (m - mpr))
    c1 += 0.0004 * math.sin(_DEG * (2 * f + m))
    c1 += -0.0004 * math.sin(_DEG * (2 * f - m))
    c1 += -0.0006 * math.sin(_DEG * (2 * f + mpr))
    c1 += 0.0010 * math.sin(_DEG * (2 * f - mpr))
    c1 += 0.0005 * math.sin(_DEG * (2 * mpr + m))

    if t < -11:
        delta_t = (
            0.001 + 0.000839 * t + 0.0002261 * t2 - 0.00000845 * t3 - 0.000000081 * t * t3
        )
    else:
        delta_t = -0.000278 + 0.000265 * t + 0.000262 * t2

    return jd1 + c1 - delta_t


def sun_longitude(jdn):
    """Apparent longitude of the Sun in radians, normalised to [0, 2π)."""
    t = (jdn - 2451545.0) / 36525  # Julian centuries from 2000-01-01 12:00 UTC
    t2 = t * t

    m = 357.52910 + 35999.05030 * t - 0.0001559 * t2 - 0.00000048 * t * t2
    l0 = 280.46645 + 36000.76983 * t + 0.0003032 * t2

    dl = (1.914600 - 0.004817 * t - 0.000014 * t2) * math.sin(_DEG * m)
    dl += (0.019993 - 0.000101 * t) * math.sin(_DEG * 2 * m) + 0.000290 * math.sin(_DEG * 3 * m)

    lon = (l0 + dl) * _DEG
    return lon - math.pi * 2 * math.floor(lon / (math.pi * 2))


def get_new_moon_day(k, tz=TIMEZONE):
    """JDN of the local calendar day holding the k-th new moon.

    `+ 0.5` moves from the JDN noon epoch to local midnight; `+ tz / 24` is
    the ONLY timezone application in this module (see module docstring).
    """
    return math.floor(new_moon(k) + 0.5 + tz / 24)


def get_sun_longitude(jdn, tz=TIMEZONE):
    """Which of the 12 solar-term sectors (0-11) the Sun occupies at local
    midnight of `jdn`. 0 = March equinox, 3 = June solstice, 6 = September
    equinox, 9 = December solstice.
    """
    return math.floor(sun_longitude(jdn - 0.5 - tz / 24) / math.pi * 6)


@lru_cache(maxsize=2048)
def get_lunar_month_11(yy, tz=TIMEZONE):
    """JDN of day 1 of lunar month 11 of solar year `yy`.

    Month 11 is by definition the month containing the December solstice --
    the anchor every other month number is measured from.

    Cached: pure, tiny key space (a few hundred years x 2 timezones), and the
    giỗ sweep calls it once per person per lunar year -- thousands of times
    for the same handful of arguments.
    """
    off = jd_from_date(31, 12, yy) - 2415021
    k = math.floor(off / SYNODIC_MONTH)
    nm = get_new_moon_day(k, tz)
    # Sector >= 9 means the solstice already passed: month 11 is the previous one.
    if get_sun_longitude(nm, tz) >= 9:
        nm = get_new_moon_day(k - 1, tz)
    return nm


@lru_cache(maxsize=2048)
def get_leap_month_offset(a11, tz=TIMEZONE):
    """Position of the intercalary month, counted from month 11 at `a11`.

    The leap month is the first month after month 11 that contains no
    principal solar term -- i.e. the first month whose solar sector repeats
    the previous month's.

    Cached for the same reason as `get_lunar_month_11`, and it matters more:
    each miss costs up to 14 `new_moon()` + `sun_longitude()` evaluations.
    """
    k = math.floor((a11 - NEW_MOON_EPOCH) / SYNODIC_MONTH + 0.5)
    i = 1
    arc = get_sun_longitude(get_new_moon_day(k + i, tz), tz)
    while True:
        last = arc
        i += 1
        arc = get_sun_longitude(get_new_moon_day(k + i, tz), tz)
        if not (arc != last and i < 14):
            break
    return i - 1


def solar_to_lunar(dd, mm, yy, tz=TIMEZONE):
    """Gregorian -> `(lunar_day, lunar_month, lunar_year, is_leap)`.

    `is_leap` is 1 when the month is intercalary, 0 otherwise. Raises
    `ValueError` outside [MIN_YEAR, MAX_YEAR].
    """
    _check_year(yy)

    day_number = jd_from_date(dd, mm, yy)
    k = math.floor((day_number - NEW_MOON_EPOCH) / SYNODIC_MONTH)

    month_start = get_new_moon_day(k + 1, tz)
    if month_start > day_number:
        month_start = get_new_moon_day(k, tz)

    a11 = get_lunar_month_11(yy, tz)
    b11 = a11
    if a11 >= month_start:
        lunar_year = yy
        a11 = get_lunar_month_11(yy - 1, tz)
    else:
        lunar_year = yy + 1
        b11 = get_lunar_month_11(yy + 1, tz)

    lunar_day = day_number - month_start + 1

    # Months elapsed since month 11. `29` (not 29.53) is the reference's
    # divisor and is safe: consecutive new moons are 29 or 30 days apart, so
    # the floor still lands on the right month index.
    diff = math.floor((month_start - a11) / 29)
    lunar_leap = 0
    lunar_month = diff + 11

    if b11 - a11 > 365:  # 13 months between the two anchors -> leap year
        leap_month_diff = get_leap_month_offset(a11, tz)
        if diff >= leap_month_diff:
            # Everything from the leap month on shifts back one number: the
            # leap month reuses the previous month's number.
            lunar_month = diff + 10
            if diff == leap_month_diff:
                lunar_leap = 1

    if lunar_month > 12:
        lunar_month -= 12
    # Months 11-12 fall in the solar year BEFORE their lunar year's Tết.
    if lunar_month >= 11 and diff < 4:
        lunar_year -= 1

    return lunar_day, lunar_month, lunar_year, lunar_leap


def _anchors(lm, ly, tz):
    """The two month-11 anchors bracketing lunar month `lm` of year `ly`.

    Months 1-10 sit between the month 11 that opened the lunar year (in solar
    year `ly - 1`) and the next one; months 11-12 sit one anchor later.
    """
    if lm < 11:
        return get_lunar_month_11(ly - 1, tz), get_lunar_month_11(ly, tz)
    return get_lunar_month_11(ly, tz), get_lunar_month_11(ly + 1, tz)


def _leap_month_number(a11, b11, tz):
    """`(month_number, offset)` of this lunar year's intercalary month, or
    `(None, None)` when it has none.

    The offset is returned alongside rather than looked up again by the
    caller: `get_leap_month_offset` is the most expensive call in the module.
    """
    if b11 - a11 <= 365:  # 12 months between anchors -> no intercalary month
        return None, None
    offset = get_leap_month_offset(a11, tz)
    leap_month = offset - 2
    if leap_month < 0:
        leap_month += 12
    return leap_month, offset


def _month_start_jd(lm, ly, is_leap, tz):
    """JDN of day 1 of the given lunar month.

    Raises `ValueError` when `is_leap` is set for a month that is not
    intercalary in `ly`: silently returning the regular month's date would
    put a giỗ a full month out, which is exactly the failure this module
    exists to prevent.
    """
    a11, b11 = _anchors(lm, ly, tz)

    off = lm - 11
    if off < 0:
        off += 12

    leap_month, leap_off = _leap_month_number(a11, b11, tz)
    if leap_month is None:
        if is_leap:
            raise ValueError('Năm âm lịch {} không có tháng nhuận.'.format(ly))
    else:
        if is_leap and lm != leap_month:
            raise ValueError(
                'Tháng {} năm {} không phải tháng nhuận.'.format(lm, ly)
            )
        # Past the intercalary month every number is one new moon later.
        if is_leap or off >= leap_off:
            off += 1

    k = math.floor(0.5 + (a11 - NEW_MOON_EPOCH) / SYNODIC_MONTH)
    return get_new_moon_day(k + off, tz)


def lunar_to_solar(ld, lm, ly, is_leap=0, tz=TIMEZONE):
    """`(lunar_day, lunar_month, lunar_year, is_leap)` -> `(dd, mm, yy)`.

    Raises `ValueError` outside the supported range or on an `is_leap` flag
    that does not match the year.
    """
    _check_lunar_year(ly)
    return jd_to_date(_month_start_jd(lm, ly, is_leap, tz) + ld - 1)


def lunar_month_length(lm, ly, is_leap=0, tz=TIMEZONE):
    """Days in a lunar month: 29 (tháng thiếu) or 30 (tháng đủ).

    Measured as the gap to the next new moon, not by probing day 30 --
    `lunar_to_solar` is pure arithmetic on the month start and would happily
    hand back a date for a day 30 that does not exist. The giỗ rules need
    this to know when to fall back to day 29.
    """
    _check_lunar_year(ly)
    start = _month_start_jd(lm, ly, is_leap, tz)
    k = math.floor((start - NEW_MOON_EPOCH) / SYNODIC_MONTH + 0.5)
    return get_new_moon_day(k + 1, tz) - start


def has_leap_month(lm, ly, tz=TIMEZONE):
    """True when lunar year `ly` carries an intercalary copy of month `lm`."""
    _check_lunar_year(ly)
    a11, b11 = _anchors(lm, ly, tz)
    return _leap_month_number(a11, b11, tz)[0] == lm
