"""Test vectors for `giapha.services.vn_lunar`.

SOURCING POLICY
---------------
The plan requires every vector to be traceable. Each below carries one of
four provenance tags, and nothing is asserted on the strength of "the code
said so":

  [TET]    Lunar New Year is public record -- Tết falls on lunar 1/1 by
           definition, and the solar date of each Tết is independently
           documented (Wikipedia "Tết", any Vietnamese wall calendar). These
           are the load-bearing vectors: they pin the calendar to reality.
  [TZ]     Structural proof rather than an almanac lookup. The SAME function
           is run at tz=7 and tz=8; the Vietnamese and Chinese calendars are
           known to diverge in these years, so a divergence appearing exactly
           there -- and nowhere else in the sample -- shows the UTC+7 term is
           live and correctly placed.
  [INV]    Invariants that cannot be satisfied by a plausible-looking bug:
           round-trip identity over the full range, month lengths, range
           guards.
  [REF]    Checked against OTHER code: `lunarcalendar` (the independently
           written UTC+8 implementation already vendored for `apis/`), and
           Hồ Ngọc Đức's own `amlich.js` run under node in a full 146.097-day
           differential during the phase 5 code review.

A NOTE ON 1985 -- DO NOT "FIX" THIS
-----------------------------------
Vietnamese Tết 1985 was 21/01/1985; China's was 20/02/1985. The documented
VN/CN Tết divergences since Vietnam adopted UTC+7 are 1968, 1969, 1985 and
2007, and this module reproduces exactly that set.

An earlier revision of `plans/reports/researcher-260905-1610-*.md` claimed
Tết 1985 was 20/02 and that VN did not diverge that year, and `plan.md`
repeated it. Both were wrong: the researcher's "reference implementation" had
been run at tz=8, i.e. it was reading the Chinese calendar. The mechanism for
the real divergence is asserted in `test_1985_diverges_by_a_whole_month`
below -- the two zones select different new moons for the December-1984
solstice month, making the year 384 days (leap) in Vietnam and 355 days (no
leap) in China.

If a future reader "corrects" 1985 back to 20/02 on the strength of an old
report, every 1985 giỗ shifts by a month.
"""

import datetime as dt

from django.test import SimpleTestCase

from giapha.services import vn_lunar


class TetVectorTests(SimpleTestCase):
    """[TET] Solar date of Tết -> lunar 1/1. The anchor set."""

    # (solar dd, mm, yy) -> lunar (day, month, year, is_leap)
    TET = [
        ((29, 1, 1968), 1968),   # Mậu Thân -- also a [TZ] divergence year
        ((21, 1, 1985), 1985),   # Ất Sửu   -- also a [TZ] divergence year
        ((9, 2, 1986), 1986),    # Bính Dần
        ((22, 1, 2004), 2004),   # Giáp Thân -- leap-month year, see below
        ((17, 2, 2007), 2007),   # Đinh Hợi -- also a [TZ] divergence year
        ((25, 1, 2020), 2020),   # Canh Tý
        ((12, 2, 2021), 2021),   # Tân Sửu
        ((1, 2, 2022), 2022),    # Nhâm Dần
        ((22, 1, 2023), 2023),   # Quý Mão
        ((10, 2, 2024), 2024),   # Giáp Thìn
        ((29, 1, 2025), 2025),   # Ất Tỵ
        ((17, 2, 2026), 2026),   # Bính Ngọ
    ]

    def test_solar_to_lunar_gives_first_of_first_month(self):
        for solar, lunar_year in self.TET:
            with self.subTest(solar=solar):
                self.assertEqual(
                    vn_lunar.solar_to_lunar(*solar), (1, 1, lunar_year, 0)
                )

    def test_lunar_to_solar_gives_back_the_tet_date(self):
        for solar, lunar_year in self.TET:
            with self.subTest(lunar_year=lunar_year):
                self.assertEqual(vn_lunar.lunar_to_solar(1, 1, lunar_year), solar)


class TimezoneDivergenceTests(SimpleTestCase):
    """[TZ] The whole reason this module exists instead of `lunarcalendar`.

    If the `+ tz / 24` term in `get_new_moon_day` were dropped or hardcoded to
    8, every assertion in this class would fail while most of the suite kept
    passing -- which is precisely why these are separate tests.
    """

    def test_1968_vietnam_is_one_day_before_china(self):
        self.assertEqual(vn_lunar.lunar_to_solar(1, 1, 1968, 0, tz=7), (29, 1, 1968))
        self.assertEqual(vn_lunar.lunar_to_solar(1, 1, 1968, 0, tz=8), (30, 1, 1968))

    def test_1969_vietnam_is_one_day_before_china(self):
        self.assertEqual(vn_lunar.lunar_to_solar(1, 1, 1969, 0, tz=7), (16, 2, 1969))
        self.assertEqual(vn_lunar.lunar_to_solar(1, 1, 1969, 0, tz=8), (17, 2, 1969))

    def test_2007_vietnam_is_one_day_before_china(self):
        self.assertEqual(vn_lunar.lunar_to_solar(1, 1, 2007, 0, tz=7), (17, 2, 2007))
        self.assertEqual(vn_lunar.lunar_to_solar(1, 1, 2007, 0, tz=8), (18, 2, 2007))

    def test_1985_diverges_by_a_whole_month(self):
        """The largest documented VN/CN divergence, and its mechanism.

        Not a one-day timezone rounding: the two zones pick DIFFERENT new
        moons as the month-11 (solstice) anchor for 1984, which changes
        whether 1984-85 carries an intercalary month at all.
        """
        self.assertEqual(vn_lunar.lunar_to_solar(1, 1, 1985, 0, tz=7), (21, 1, 1985))
        self.assertEqual(vn_lunar.lunar_to_solar(1, 1, 1985, 0, tz=8), (20, 2, 1985))

        vn_span = vn_lunar.get_lunar_month_11(1985, 7) - vn_lunar.get_lunar_month_11(1984, 7)
        cn_span = vn_lunar.get_lunar_month_11(1985, 8) - vn_lunar.get_lunar_month_11(1984, 8)
        self.assertGreater(vn_span, 365)      # Vietnam: 13 months, leap year
        self.assertLessEqual(cn_span, 365)    # China: 12 months, no leap

    def test_zones_agree_on_ordinary_years(self):
        """The divergence must be rare and explainable, not noise. If tz=7 and
        tz=8 disagreed everywhere, the vectors above would prove nothing.
        """
        for year in (1986, 2004, 2020, 2021, 2022, 2023, 2024, 2025, 2026):
            with self.subTest(year=year):
                self.assertEqual(
                    vn_lunar.lunar_to_solar(1, 1, year, 0, tz=7),
                    vn_lunar.lunar_to_solar(1, 1, year, 0, tz=8),
                )


class LeapMonthTests(SimpleTestCase):
    """[TET]+[INV] Intercalary months, including dates inside one."""

    def test_2004_leap_second_month(self):
        # Nhuận tháng Hai 2004: regular month 2, then a second month 2.
        self.assertEqual(vn_lunar.solar_to_lunar(22, 2, 2004), (3, 2, 2004, 0))
        self.assertEqual(vn_lunar.solar_to_lunar(22, 3, 2004), (2, 2, 2004, 1))
        self.assertEqual(vn_lunar.solar_to_lunar(20, 4, 2004), (2, 3, 2004, 0))

    def test_leap_month_round_trips_distinctly_from_the_regular_one(self):
        regular = vn_lunar.lunar_to_solar(2, 2, 2004, 0)
        leap = vn_lunar.lunar_to_solar(2, 2, 2004, 1)
        self.assertNotEqual(regular, leap)
        self.assertEqual(leap, (22, 3, 2004))
        self.assertEqual(vn_lunar.solar_to_lunar(*leap), (2, 2, 2004, 1))

    def test_has_leap_month_identifies_the_year(self):
        for year, month in ((2004, 2), (2006, 7), (2020, 4), (2023, 2), (2025, 6)):
            with self.subTest(year=year):
                self.assertTrue(vn_lunar.has_leap_month(month, year))
                # Only that one month leaps.
                others = [m for m in range(1, 13) if m != month
                          and vn_lunar.has_leap_month(m, year)]
                self.assertEqual(others, [])

    def test_year_without_leap_month(self):
        self.assertEqual(
            [m for m in range(1, 13) if vn_lunar.has_leap_month(m, 2021)], []
        )

    def test_leap_flag_on_a_non_leap_month_is_rejected(self):
        """Silently returning the regular month's date would put a giỗ a full
        month out -- the exact failure this module exists to prevent.
        """
        with self.assertRaises(ValueError):
            vn_lunar.lunar_to_solar(2, 5, 2004, 1)   # 2004 leaps month 2, not 5
        with self.assertRaises(ValueError):
            vn_lunar.lunar_to_solar(2, 5, 2021, 1)   # 2021 has no leap month


class MonthLengthTests(SimpleTestCase):
    """[INV] A lunar month is 29 (thiếu) or 30 (đủ) days -- never anything
    else. The giỗ day-30 rule depends on this being exact.
    """

    def test_every_month_1900_to_2100_is_29_or_30_days(self):
        for year in range(1900, 2101):
            for month in range(1, 13):
                length = vn_lunar.lunar_month_length(month, year)
                if length not in (29, 30):
                    self.fail('{}/{} -> {} days'.format(month, year, length))

    def test_length_matches_the_gap_to_the_next_month(self):
        for year, month in ((2023, 3), (2024, 3), (2025, 3), (2026, 8)):
            with self.subTest(year=year, month=month):
                first = vn_lunar.lunar_to_solar(1, month, year)
                next_month = month + 1 if month < 12 else 1
                next_year = year if month < 12 else year + 1
                nxt = vn_lunar.lunar_to_solar(1, next_month, next_year)
                gap = (dt.date(nxt[2], nxt[1], nxt[0])
                       - dt.date(first[2], first[1], first[0])).days
                self.assertEqual(vn_lunar.lunar_month_length(month, year), gap)


class RoundTripTests(SimpleTestCase):
    """[INV] The strongest single check available without an almanac.

    An off-by-one in the k -> month mapping, the leap-month shift, or the
    year-boundary correction breaks round-trip identity somewhere in 400
    years. Sampling every 11 days covers all lunar month positions and every
    leap month in the range while staying fast.
    """

    def test_round_trip_over_the_full_supported_range(self):
        day = dt.date(vn_lunar.MIN_YEAR, 1, 1)
        end = dt.date(vn_lunar.MAX_YEAR, 12, 31)
        step = dt.timedelta(days=11)
        checked = 0
        while day <= end:
            lunar = vn_lunar.solar_to_lunar(day.day, day.month, day.year)
            back = vn_lunar.lunar_to_solar(*lunar)
            if back != (day.day, day.month, day.year):
                self.fail('{} -> {} -> {}'.format(day, lunar, back))
            checked += 1
            day += step
        self.assertGreater(checked, 13000)

    def test_consecutive_days_advance_the_lunar_day_by_one(self):
        """Catches a month boundary landing on the wrong day: within a month
        the lunar day must increment in lockstep with the solar one.
        """
        day = dt.date(2026, 1, 1)
        previous = vn_lunar.solar_to_lunar(day.day, day.month, day.year)
        for _ in range(400):
            day += dt.timedelta(days=1)
            current = vn_lunar.solar_to_lunar(day.day, day.month, day.year)
            if current[1] == previous[1] and current[3] == previous[3]:
                self.assertEqual(current[0], previous[0] + 1)
            else:
                self.assertEqual(current[0], 1)  # new month starts at day 1
            previous = current


class RangeGuardTests(SimpleTestCase):
    """[INV] Out of range must raise, never return a plausible wrong date."""

    def test_boundaries_are_inclusive(self):
        """[REF] Both values were confirmed against Hồ Ngọc Đức's own
        `amlich.js` run under node, in a full differential over every day of
        1800-2199 (see the phase 5 code review report) -- not read off this
        implementation.
        """
        self.assertEqual(vn_lunar.solar_to_lunar(1, 1, 1800), (7, 12, 1799, 0))
        self.assertEqual(vn_lunar.solar_to_lunar(31, 12, 2199), (14, 11, 2199, 0))

    def test_boundary_dates_round_trip(self):
        for solar in ((1, 1, 1800), (31, 12, 2199)):
            with self.subTest(solar=solar):
                self.assertEqual(
                    vn_lunar.lunar_to_solar(*vn_lunar.solar_to_lunar(*solar)), solar
                )

    def test_outside_the_range_raises(self):
        for year in (1799, 1700, 2200, 2300):
            with self.subTest(year=year):
                with self.assertRaises(ValueError):
                    vn_lunar.solar_to_lunar(1, 1, year)

    def test_lunar_year_guard_allows_the_straddling_year(self):
        """Solar 1800-01-01 is lunar 1799 -- rejecting lunar 1799 outright
        would make the boundary round-trip impossible.
        """
        self.assertEqual(vn_lunar.lunar_to_solar(7, 12, 1799), (1, 1, 1800))
        with self.assertRaises(ValueError):
            vn_lunar.lunar_to_solar(1, 1, 1798)


class JulianDayTests(SimpleTestCase):
    """[INV] The arithmetic layer everything else is built on."""

    def test_known_julian_day_numbers(self):
        # 2000-01-01 is JDN 2451545 (standard J2000.0 epoch reference).
        self.assertEqual(vn_lunar.jd_from_date(1, 1, 2000), 2451545)
        self.assertEqual(vn_lunar.jd_to_date(2451545), (1, 1, 2000))

    def test_jd_round_trips_and_advances_one_per_day(self):
        day = dt.date(1800, 1, 1)
        previous = vn_lunar.jd_from_date(day.day, day.month, day.year)
        for _ in range(2000):
            day += dt.timedelta(days=1)
            current = vn_lunar.jd_from_date(day.day, day.month, day.year)
            self.assertEqual(current, previous + 1)
            self.assertEqual(vn_lunar.jd_to_date(current), (day.day, day.month, day.year))
            previous = current

    def test_floor_not_truncate_for_pre_1900_dates(self):
        """Python's `int()` truncates toward zero; the reference floors. `k`
        goes negative before 1900, so `int()` would shift month boundaries
        for a whole century. This vector fails loudly if anyone "simplifies"
        `math.floor` away.
        """
        self.assertEqual(vn_lunar.solar_to_lunar(15, 6, 1850), (6, 5, 1850, 0))
        self.assertEqual(vn_lunar.lunar_to_solar(6, 5, 1850), (15, 6, 1850))


class ChineseCalendarCrossCheckTests(SimpleTestCase):
    """[REF] The spec's step 4: where Vietnam and China agree, this module
    must agree with `lunarcalendar` -- the independently-written UTC+8
    implementation already vendored for `apis/`.

    This is the only assertion in the file that checks the algorithm against
    OTHER code rather than against itself. `TimezoneDivergenceTests` compares
    tz=7 with tz=8 of this same module, which proves the timezone term is
    wired up but would pass unchanged if both branches were wrong in the same
    way. This class closes that gap.
    """

    def _lunarcalendar_date(self, day):
        from lunarcalendar import Converter, Solar

        lunar = Converter.Solar2Lunar(Solar(day.year, day.month, day.day))
        return lunar.day, lunar.month, lunar.year, int(bool(lunar.isleap))

    def test_matches_lunarcalendar_at_utc8_except_on_divergence_years(self):
        """Sampled every 13 days over 1950-2050, which `lunarcalendar`
        supports. Run at tz=8 so ONLY the timezone differs between the two
        implementations; any mismatch is then an algorithm bug, not a
        Vietnam/China difference.
        """
        day = dt.date(1950, 1, 1)
        end = dt.date(2050, 12, 31)
        mismatches = []
        checked = 0
        while day <= end:
            mine = vn_lunar.solar_to_lunar(day.day, day.month, day.year, tz=8)
            theirs = self._lunarcalendar_date(day)
            if mine != theirs:
                mismatches.append((day, mine, theirs))
            checked += 1
            day += dt.timedelta(days=13)

        self.assertGreater(checked, 2500)
        self.assertEqual(mismatches, [], '{} mismatches vs lunarcalendar at tz=8, '
                                         'first few: {}'.format(len(mismatches),
                                                                mismatches[:5]))

    def test_vietnam_differs_from_lunarcalendar_on_the_known_years(self):
        """The flip side: at tz=7 this module must NOT match `lunarcalendar`
        on the documented divergence dates. If it did, the Vietnamese
        calendar would be silently collapsing into the Chinese one.
        """
        for day in (dt.date(1968, 1, 29), dt.date(2007, 2, 17), dt.date(1985, 1, 21)):
            with self.subTest(day=day):
                mine = vn_lunar.solar_to_lunar(day.day, day.month, day.year)
                self.assertEqual(mine[:2], (1, 1))  # mùng 1 Tết in Vietnam
                self.assertNotEqual(mine, self._lunarcalendar_date(day))
