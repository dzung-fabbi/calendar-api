"""Pythagorean numerology helpers for the `so-hoc` endpoint.

The letter table used to be rebuilt inside the view on every request; it is a
constant and lives here now.
"""

# Vietnamese diacritics -> their ASCII base letter. Both strings are 134
# characters with no repeats, so this is a faithful 1:1 mapping.
_ACCENTED = (
    'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ'
)
_UNACCENTED = (
    'AAAAEEEIIOOOOUUYaaaaeeeiioooouuyAaDdIiUuOoUuAaAaAaAaAaAaAaAaAaAaAaAaEeEeEeEeEeEeEeEeIiIiOoOoOoOoOoOoOoOoOoOoOoOoUuUuUuUuUuUuUuYyYyYyYy'
)
_ACCENT_TABLE = str.maketrans(_ACCENTED, _UNACCENTED)

VOWELS = frozenset('aeiou')

# Letter -> numerology value: a=1..i=9, then the cycle repeats.
LETTER_VALUES = {
    chr(ord('a') + offset): (offset % 9) + 1
    for offset in range(26)
}

MASTER_NUMBERS = (11, 22, 33)


def strip_accents(text):
    """Drop Vietnamese diacritics, leaving other characters untouched."""
    return text.translate(_ACCENT_TABLE)


def is_vowel(char):
    return char in VOWELS


def digit_sum(value):
    """Sum the decimal digits of `value` once, without further reduction.

    Raises ValueError on any non-digit character, exactly as the original
    `SoHocAPIView.get_sum` did. Callers are responsible for validating input;
    see the endpoint's parameter checks.
    """
    return sum(int(digit) for digit in str(value))


def reduce_to_single_digit(value):
    """Reduce to 1-9 by summing digits repeatedly.

    A numerology number is a single digit; one pass is not always enough
    (199 -> 19 needs a second pass to reach 1). The original summed once, so
    any input whose digits summed past 9 was left as a two-digit "number".
    """
    result = digit_sum(value)
    while result > 9:
        result = digit_sum(result)
    return result


def reduce_keeping_master(value):
    """Reduce to 1-9, but stop on the master numbers 11, 22 and 33."""
    result = digit_sum_master(value)
    while result > 9 and result not in MASTER_NUMBERS:
        result = digit_sum_master(result)
    return result


def digit_sum_master(value):
    """Digit sum that leaves the master numbers 11/22/33 intact."""
    if value in MASTER_NUMBERS:
        return value
    return digit_sum(value)


def letter_values(text):
    """The numerology values of every alphabetic character in `text`.

    Returns `(total, vowel_total, consonant_total, values, first_vowel_value)`.
    `text` is expected to be accent-stripped and lower-cased already.
    """
    total = vowel_total = consonant_total = 0
    values = []
    first_vowel_value = ''
    for char in text:
        value = LETTER_VALUES.get(char)
        if value is None:
            continue
        if is_vowel(char):
            if first_vowel_value == '':
                first_vowel_value = value
            vowel_total += value
        else:
            consonant_total += value
        total += value
        values.append(value)
    return total, vowel_total, consonant_total, values, first_vowel_value
