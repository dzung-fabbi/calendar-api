"""Scoring a day as good or bad from its things-to-do and star lists."""

from collections import namedtuple

VERY_GOOD_TEXT = "Ngày rất tốt"
GOOD_TEXT = "Ngày tốt"

# Mirrors the fields of the DateConfig model. Used when no row exists yet; the
# values are the constants that used to be hard-coded in the view.
RatingConfig = namedtuple(
    'RatingConfig',
    ['very_good_from', 'good_from', 'ugly_from', 'factor_1', 'factor_2'],
)

DEFAULT_CONFIG = RatingConfig(
    very_good_from=1.5, good_from=1.0, ugly_from=0.5, factor_1=1.0, factor_2=2.0,
)


def config_from(date_config):
    """Adapt a DateConfig row (or None) to the tuple `rate_day` expects."""
    if date_config is None:
        return DEFAULT_CONFIG
    return RatingConfig(
        very_good_from=date_config.very_good_from,
        good_from=date_config.good_from,
        ugly_from=date_config.ugly_from,
        factor_1=date_config.factor_1,
        factor_2=date_config.factor_2,
    )


def _count(csv_text):
    """Number of comma-separated entries.

    An empty string counts as 1, which is what makes a day with no ugly stars
    score well rather than blowing up on a division. Preserved deliberately.
    """
    return len(csv_text.split(','))


def rate_day(good_thing, ugly_thing, good_star, ugly_star, config=DEFAULT_CONFIG):
    """Rate a day. Returns {'is_good': bool, and when scored, 'percent'/'text'}.

    `percent` is the weighted mean of two ratios -- things-to-do against
    things-to-avoid (weighted by `factor_2`) and good stars against bad ones
    (weighted by `factor_1`). With the shipped defaults 2 and 1 this is
    identical to the arithmetic that used to be hard-coded here.

    The original tested `good_star` twice; the second test was meant to be a
    third condition, not a check on `ugly_star`. Requiring `ugly_star` would
    reject any day that has no bad stars at all -- precisely the best days --
    so the redundant test is simply dropped rather than "corrected".
    """
    if not good_thing or not good_star or not ugly_thing:
        return {"is_good": False}

    weight_total = config.factor_1 + config.factor_2
    percent = (
        (_count(good_thing) / _count(ugly_thing)) * config.factor_2
        + (_count(good_star) / _count(ugly_star)) * config.factor_1
    ) / weight_total

    if percent > config.very_good_from:
        return {"is_good": True, "percent": percent, "text": VERY_GOOD_TEXT}

    if config.good_from <= percent <= config.very_good_from:
        return {"is_good": True, "percent": percent, "text": GOOD_TEXT}

    if config.good_from > percent >= config.ugly_from:
        return {"is_good": False, "percent": percent}

    return {"is_good": False}
