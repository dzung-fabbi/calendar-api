"""Pure-function tests for `giapha.services.gio` -- the three customary giỗ
rules and the window sweep. API-level coverage lives in `test_gio_api.py`.

Every expected solar date here is derived from `vn_lunar`, which
`test_vn_lunar.py` pins to independently-documented Tết dates. These tests
are about the CUSTOM applied on top of the conversion, not the conversion.
"""

import datetime as dt

from django.test import SimpleTestCase

from giapha.services import vn_lunar
from giapha.services.gio import (
    gio_occurrence,
    gio_occurrences_in_range,
    lunar_years_covering,
    today_vn,
)


def solar(dd, mm, yy):
    return dt.date(yy, mm, dd)


class Day30RuleTests(SimpleTestCase):
    """Rule 1: died on day 30; in a year where that month runs 29 days the
    giỗ moves to day 29 and is flagged.
    """

    def test_full_month_keeps_day_30(self):
        # Lunar month 3 is 30 days (đủ) in 2020 and 2022.
        for year in (2020, 2022):
            with self.subTest(year=year):
                self.assertEqual(vn_lunar.lunar_month_length(3, year), 30)
                occurrence = gio_occurrence(30, 3, year)
                self.assertEqual(occurrence.day, 30)
                self.assertFalse(occurrence.adjusted)
                self.assertEqual(
                    occurrence.solar_date, solar(*vn_lunar.lunar_to_solar(30, 3, year))
                )

    def test_short_month_falls_back_to_day_29(self):
        # Lunar month 3 is 29 days (thiếu) in 2023 and 2024.
        for year in (2023, 2024):
            with self.subTest(year=year):
                self.assertEqual(vn_lunar.lunar_month_length(3, year), 29)
                occurrence = gio_occurrence(30, 3, year)
                self.assertEqual(occurrence.day, 29)
                self.assertTrue(occurrence.adjusted)
                self.assertEqual(
                    occurrence.solar_date, solar(*vn_lunar.lunar_to_solar(29, 3, year))
                )

    def test_day_29_is_never_adjusted(self):
        """The fallback must trigger on day 30 only -- a day-29 giỗ exists in
        every month and moving it would be a bug the family would notice.
        """
        for year in (2023, 2024):
            with self.subTest(year=year):
                self.assertFalse(gio_occurrence(29, 3, year).adjusted)

    def test_same_person_adjusts_only_in_the_short_years(self):
        adjusted = {
            year: gio_occurrence(30, 3, year).adjusted for year in range(2020, 2027)
        }
        self.assertEqual(
            adjusted,
            {2020: False, 2021: False, 2022: False,
             2023: True, 2024: True, 2025: False, 2026: False},
        )

    def test_day_30_in_month_12_adjusts_in_short_years(self):
        """Month 12 (Chap - last lunar month) also has years with only 29 days.
        The fallback rule must apply here too. Month 12 is 29 days in 2026.
        """
        self.assertEqual(vn_lunar.lunar_month_length(12, 2026), 29)
        occurrence = gio_occurrence(30, 12, 2026)
        self.assertEqual(occurrence.day, 29)
        self.assertTrue(occurrence.adjusted)

    def test_day_30_in_month_11_adjusts_in_short_years(self):
        """Month 11 also occasionally has only 29 days. Find a year where this
        occurs and verify the fallback works.
        """
        # Month 11 is 29 days in certain years. Find one and test.
        for test_year in range(2000, 2050):
            if vn_lunar.lunar_month_length(11, test_year) == 29:
                occurrence = gio_occurrence(30, 11, test_year)
                self.assertEqual(occurrence.day, 29)
                self.assertTrue(occurrence.adjusted)
                return
        self.fail("No year found with 29-day month 11 in range 2000-2050")


class LeapMonthRuleTests(SimpleTestCase):
    """Rules 2 and 3: a giỗ is observed in the regular month, always.

    Whether the DEATH fell in an intercalary month, and whether the CURRENT
    year happens to have one, are both irrelevant to where the giỗ lands.
    """

    def test_gio_uses_the_regular_month_in_a_leap_year(self):
        # 2023 leaps month 2; a month-2 giỗ belongs to the regular month 2.
        self.assertTrue(vn_lunar.has_leap_month(2, 2023))
        occurrence = gio_occurrence(10, 2, 2023)
        self.assertEqual(
            occurrence.solar_date, solar(*vn_lunar.lunar_to_solar(10, 2, 2023, 0))
        )
        self.assertNotEqual(
            occurrence.solar_date, solar(*vn_lunar.lunar_to_solar(10, 2, 2023, 1))
        )

    def test_death_in_a_leap_month_still_observes_the_regular_month(self):
        """Someone who died in nhuận tháng Hai 2004 is remembered in the
        regular month 2 of later years -- otherwise the family would wait
        years for the next leap month.
        """
        for year in (2005, 2006, 2023):
            with self.subTest(year=year):
                occurrence = gio_occurrence(10, 2, year)
                self.assertEqual(
                    occurrence.solar_date,
                    solar(*vn_lunar.lunar_to_solar(10, 2, year, 0)),
                )

    def test_a_leap_year_never_yields_two_occurrences(self):
        window = (dt.date(2023, 1, 1), dt.date(2023, 12, 31))
        found = gio_occurrences_in_range(10, 2, *window)
        self.assertEqual(len(found), 1)

    def test_leap_month_death_observed_in_another_leap_year(self):
        """Two different lunar years both leap the same month. Someone who
        died in nhuận tháng 2 (leap month 2) of 2004 will have anniversaries
        in regular month 2 of every year after, regardless of whether that year
        also leaps month 2. This tests that checking the calendar in 2023
        (another leap-month-2 year) correctly uses the REGULAR month 2, not
        confused by 2023 having a leap month 2.
        """
        self.assertTrue(vn_lunar.has_leap_month(2, 2004))
        self.assertTrue(vn_lunar.has_leap_month(2, 2023))
        # Anniversary is in regular month 2 in both years.
        occ_2023 = gio_occurrence(10, 2, 2023)
        self.assertEqual(
            occ_2023.solar_date,
            solar(*vn_lunar.lunar_to_solar(10, 2, 2023, 0))  # is_leap=0
        )


class WindowSweepTests(SimpleTestCase):
    """One person can have zero, one, or two giỗ in a given solar window."""

    def test_one_occurrence_in_an_ordinary_year(self):
        found = gio_occurrences_in_range(12, 8, dt.date(2026, 1, 1), dt.date(2026, 12, 31))
        self.assertEqual(len(found), 1)

    def test_two_occurrences_in_one_solar_year(self):
        """A month-12 giỗ falls in early January and again in late December of
        2022 -- 354 days apart, both inside the same solar year. Code that
        assumed one giỗ per person per year would drop the December one.
        """
        found = gio_occurrences_in_range(1, 12, dt.date(2022, 1, 1), dt.date(2022, 12, 31))
        self.assertEqual([o.solar_date for o in found],
                         [dt.date(2022, 1, 3), dt.date(2022, 12, 23)])
        self.assertEqual([o.lunar_year for o in found], [2021, 2022])

    def test_month_11_can_also_double_up(self):
        found = gio_occurrences_in_range(20, 11, dt.date(2024, 1, 1), dt.date(2024, 12, 31))
        self.assertEqual([o.solar_date for o in found],
                         [dt.date(2024, 1, 1), dt.date(2024, 12, 20)])

    def test_no_occurrence_in_a_narrow_window(self):
        found = gio_occurrences_in_range(1, 1, dt.date(2026, 6, 1), dt.date(2026, 6, 30))
        self.assertEqual(found, [])

    def test_window_bounds_are_inclusive(self):
        exact = gio_occurrences_in_range(1, 12, dt.date(2022, 1, 3), dt.date(2022, 1, 3))
        self.assertEqual(len(exact), 1)
        just_after = gio_occurrences_in_range(1, 12, dt.date(2022, 1, 4), dt.date(2022, 1, 4))
        self.assertEqual(just_after, [])

    def test_hoisted_lunar_years_match_the_computed_ones(self):
        """The view hoists `lunar_years_covering` out of its per-person loop;
        that optimisation must not change the answer.
        """
        start, end = dt.date(2022, 1, 1), dt.date(2022, 12, 31)
        years = lunar_years_covering(start, end)
        for day, month in ((1, 12), (20, 11), (12, 8), (5, 3)):
            with self.subTest(day=day, month=month):
                self.assertEqual(
                    gio_occurrences_in_range(day, month, start, end),
                    gio_occurrences_in_range(day, month, start, end, lunar_years=years),
                )

    def test_window_narrowly_catches_both_double_gio(self):
        """Month 12 giỗ appears twice in 2022: Jan 3 and Dec 23. A tight
        window around the exact start and end dates must capture both.
        """
        found = gio_occurrences_in_range(
            1, 12, dt.date(2022, 1, 3), dt.date(2022, 12, 23)
        )
        self.assertEqual(len(found), 2)
        self.assertEqual([o.solar_date for o in found],
                         [dt.date(2022, 1, 3), dt.date(2022, 12, 23)])

    def test_window_just_before_first_double_gio_finds_nothing(self):
        """Same month 12 person, but the window ends one day before the
        January occurrence.
        """
        found = gio_occurrences_in_range(
            1, 12, dt.date(2022, 1, 1), dt.date(2022, 1, 2)
        )
        self.assertEqual(found, [])

    def test_window_just_after_last_double_gio_finds_nothing(self):
        """Same month 12 person, but the window starts one day after the
        December occurrence.
        """
        found = gio_occurrences_in_range(
            1, 12, dt.date(2022, 12, 24), dt.date(2022, 12, 31)
        )
        self.assertEqual(found, [])


class RangeGuardTests(SimpleTestCase):
    """A year `vn_lunar` cannot compute must be skipped, not crash the sweep."""

    def test_year_outside_the_supported_range_returns_none(self):
        self.assertIsNone(gio_occurrence(10, 3, vn_lunar.MAX_YEAR + 1))
        self.assertIsNone(gio_occurrence(10, 3, vn_lunar.MIN_YEAR - 2))

    def test_sweep_near_the_upper_bound_does_not_raise(self):
        found = gio_occurrences_in_range(
            10, 3, dt.date(vn_lunar.MAX_YEAR, 1, 1), dt.date(vn_lunar.MAX_YEAR, 12, 31)
        )
        self.assertEqual(len(found), 1)


class TodayVnTests(SimpleTestCase):
    """`days_until` is meaningless if "today" is the server's UTC date."""

    def test_today_is_the_vietnam_date(self):
        expected = (dt.datetime.now(dt.timezone.utc)
                    + dt.timedelta(hours=7)).date()
        self.assertEqual(today_vn(), expected)
