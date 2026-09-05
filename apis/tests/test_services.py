"""Unit tests for the extracted calculation services."""

import datetime as dt

from django.test import SimpleTestCase

from apis.constant import CAN_CHI
from apis.models.choices import lunar_day
from apis.services.can_chi import (
    GIAP_TY_EPOCH,
    can_chi_for_date,
    lunar_month_solar_range,
)
from apis.services.day_rating import DEFAULT_CONFIG, RatingConfig, rate_day
from apis.services.numerology import (
    LETTER_VALUES,
    letter_values,
    reduce_keeping_master,
    reduce_to_single_digit,
    strip_accents,
)


class CanChiTests(SimpleTestCase):
    def test_epoch_is_giap_ty(self):
        self.assertEqual('Giáp Tý', can_chi_for_date(GIAP_TY_EPOCH))

    def test_cycle_advances_and_repeats_every_60_days(self):
        self.assertEqual('Ất Sửu', can_chi_for_date(GIAP_TY_EPOCH + dt.timedelta(days=1)))
        self.assertEqual('Quý Hợi', can_chi_for_date(GIAP_TY_EPOCH + dt.timedelta(days=59)))
        self.assertEqual('Giáp Tý', can_chi_for_date(GIAP_TY_EPOCH + dt.timedelta(days=60)))

    def test_works_before_the_epoch(self):
        self.assertEqual('Quý Hợi', can_chi_for_date(GIAP_TY_EPOCH - dt.timedelta(days=1)))

    def test_constant_matches_the_model_choices(self):
        """The generated cycle must equal the choices stored in the database."""
        self.assertEqual([value for value, _label in lunar_day], CAN_CHI)

    def test_lunar_month_is_29_or_30_days(self):
        for month in range(1, 13):
            first, last = lunar_month_solar_range(2026, month)
            length = (last - first).days + 1
            self.assertIn(
                length, (29, 30),
                'lunar month {} came out {} days'.format(month, length),
            )


class NumerologyTests(SimpleTestCase):
    def test_strip_accents_maps_vietnamese_to_ascii(self):
        self.assertEqual('Nguyen Van An', strip_accents('Nguyễn Văn An'))
        self.assertEqual('Dao Thi Huong', strip_accents('Đào Thị Hường'))

    def test_strip_accents_leaves_other_characters_alone(self):
        self.assertEqual('Mary-Jane 3', strip_accents('Mary-Jane 3'))

    def test_letter_values_cycle_one_to_nine(self):
        self.assertEqual(1, LETTER_VALUES['a'])
        self.assertEqual(9, LETTER_VALUES['i'])
        self.assertEqual(1, LETTER_VALUES['j'])
        self.assertEqual(8, LETTER_VALUES['z'])

    def test_reduce_needs_more_than_one_pass(self):
        """The original summed digits once, so 199 came back as 19."""
        self.assertEqual(1, reduce_to_single_digit(199))
        self.assertEqual(6, reduce_to_single_digit(33))
        self.assertEqual(9, reduce_to_single_digit(9))

    def test_reduce_keeping_master_stops_on_master_numbers(self):
        self.assertEqual(11, reduce_keeping_master(11))
        self.assertEqual(22, reduce_keeping_master(22))
        self.assertEqual(33, reduce_keeping_master(33))
        # 39 -> 12 -> 3: not a master number, so it reduces all the way.
        self.assertEqual(3, reduce_keeping_master(39))

    def test_letter_values_splits_vowels_and_consonants(self):
        total, vowels, consonants, values, first_vowel = letter_values('an')
        self.assertEqual(1 + 5, total)
        self.assertEqual(1, vowels)
        self.assertEqual(5, consonants)
        self.assertEqual([1, 5], values)
        self.assertEqual(1, first_vowel)

    def test_letter_values_ignores_non_letters(self):
        total, _vowels, _consonants, values, _first = letter_values('a b-1')
        self.assertEqual(1 + 2, total)
        self.assertEqual([1, 2], values)


class DayRatingTests(SimpleTestCase):
    GOOD_THINGS = 'Cưới hỏi,Khai trương,Xuất hành'
    BAD_THINGS = 'An táng'
    GOOD_STARS = 'Thiên Đức,Nguyệt Đức'
    BAD_STARS = 'Thiên Cương'

    def test_rates_a_strong_day_as_very_good(self):
        result = rate_day(self.GOOD_THINGS, self.BAD_THINGS, self.GOOD_STARS, self.BAD_STARS)
        self.assertTrue(result['is_good'])
        self.assertEqual('Ngày rất tốt', result['text'])

    def test_day_with_no_ugly_stars_still_scores(self):
        """Requiring `ugly_star` would reject the best days outright."""
        result = rate_day(self.GOOD_THINGS, self.BAD_THINGS, self.GOOD_STARS, '')
        self.assertTrue(result['is_good'])

    def test_missing_good_data_is_not_rated(self):
        self.assertFalse(
            rate_day('', self.BAD_THINGS, self.GOOD_STARS, self.BAD_STARS)['is_good'])
        self.assertFalse(
            rate_day(self.GOOD_THINGS, self.BAD_THINGS, '', self.BAD_STARS)['is_good'])
        self.assertFalse(
            rate_day(self.GOOD_THINGS, '', self.GOOD_STARS, self.BAD_STARS)['is_good'])

    def test_thresholds_come_from_the_config(self):
        """Raising very_good_from demotes a day the defaults called great."""
        strict = RatingConfig(
            very_good_from=5.0, good_from=1.0, ugly_from=0.5, factor_1=1.0, factor_2=2.0,
        )
        default_result = rate_day(
            self.GOOD_THINGS, self.BAD_THINGS, self.GOOD_STARS, self.BAD_STARS,
            DEFAULT_CONFIG,
        )
        strict_result = rate_day(
            self.GOOD_THINGS, self.BAD_THINGS, self.GOOD_STARS, self.BAD_STARS, strict,
        )
        self.assertEqual('Ngày rất tốt', default_result['text'])
        self.assertEqual('Ngày tốt', strict_result['text'])

    def test_weights_come_from_the_config(self):
        """factor_1 / factor_2 change the balance between the two ratios."""
        things_only = RatingConfig(
            very_good_from=1.5, good_from=1.0, ugly_from=0.5, factor_1=0.0, factor_2=1.0,
        )
        result = rate_day(
            self.GOOD_THINGS, self.BAD_THINGS, self.GOOD_STARS, self.BAD_STARS,
            things_only,
        )
        # 3 things to do against 1 to avoid; the star ratio is weighted out.
        self.assertEqual(3.0, result['percent'])
