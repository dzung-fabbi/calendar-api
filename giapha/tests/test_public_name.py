"""Unit tests for `services.public_name` (phase 9). Pure functions, no
database -- `SimpleTestCase`.
"""

from django.test import SimpleTestCase

from giapha.services.public_name import LIVING_NAME_PLACEHOLDER, abbreviate_name, public_display_name


class AbbreviateNameTests(SimpleTestCase):
    def test_multi_syllable_vietnamese_name(self):
        self.assertEqual('Nguyễn Đình A.', abbreviate_name('Nguyễn Đình An'))

    def test_longer_multi_syllable_name(self):
        self.assertEqual('Trần Thị Bích H.', abbreviate_name('Trần Thị Bích Hương'))

    def test_single_word_name(self):
        # 'An' has a 2-character given name -- 'A.' genuinely hides the
        # 'n', this is NOT the L3 no-op case (see the placeholder tests
        # below for when the given name itself is only 1 character).
        self.assertEqual('A.', abbreviate_name('An'))

    def test_extra_internal_whitespace_is_collapsed(self):
        self.assertEqual('Nguyễn Đình A.', abbreviate_name('  Nguyễn   Đình   An  '))

    def test_empty_string_returns_empty_string_without_raising(self):
        self.assertEqual('', abbreviate_name(''))

    def test_whitespace_only_returns_empty_string(self):
        self.assertEqual('', abbreviate_name('   '))

    def test_initial_is_uppercased_even_for_lowercase_input(self):
        # Intended, not a bug: the initial is presentational, matching
        # Vietnamese name capitalisation conventions, regardless of the
        # input's own casing.
        self.assertEqual('nguyen dinh A.', abbreviate_name('nguyen dinh an'))

    def test_single_character_given_name_in_a_multi_word_name_is_placeholder(self):
        # Security fix (phase-9 review L3): a 1-character given name
        # abbreviates to itself + '.', i.e. no actual disguising -- the
        # whole name (not just the given-name token) must fall back to
        # the placeholder instead of publishing 'rest' + the bare name.
        self.assertEqual(LIVING_NAME_PLACEHOLDER, abbreviate_name('李 小 龍'))

    def test_single_character_single_word_name_is_placeholder(self):
        self.assertEqual(LIVING_NAME_PLACEHOLDER, abbreviate_name('A'))

    def test_single_character_given_name_with_trailing_period_is_placeholder(self):
        # Regression for the cosmetic double-period bug: a 1-character
        # given name that happens to already be '.' used to abbreviate to
        # '..'; it must fall into the same placeholder path as any other
        # 1-character given name, never emit a bare '.' or '..'.
        self.assertEqual(LIVING_NAME_PLACEHOLDER, abbreviate_name('.'))

    def test_never_raises_on_non_string_free_input(self):
        # Whitespace/empty already covered above; this rounds out "do not
        # crash on any input" with a name made only of separators.
        self.assertEqual('', abbreviate_name('\t\n  '))


class PublicDisplayNameTests(SimpleTestCase):
    def test_living_and_hidden_returns_abbreviation(self):
        name = public_display_name('Nguyễn Đình An', is_living=True, hide_living_details=True)
        self.assertEqual('Nguyễn Đình A.', name)

    def test_living_and_not_hidden_returns_full_name(self):
        name = public_display_name('Nguyễn Đình An', is_living=True, hide_living_details=False)
        self.assertEqual('Nguyễn Đình An', name)

    def test_dead_always_returns_full_name_regardless_of_flag(self):
        self.assertEqual(
            'Nguyễn Đình An',
            public_display_name('Nguyễn Đình An', is_living=False, hide_living_details=True),
        )
        self.assertEqual(
            'Nguyễn Đình An',
            public_display_name('Nguyễn Đình An', is_living=False, hide_living_details=False),
        )
