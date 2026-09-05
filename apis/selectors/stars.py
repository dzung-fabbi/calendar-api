"""Bulk fetch helpers that keep the star lookups off the per-row path.

Each function here replaces a loop that used to issue one or two queries per
day. They return plain dicts/lists so the views can assemble responses without
touching the ORM again.
"""

from collections import defaultdict

from django.db.models import Prefetch

from apis.models import (
    SAO_HOUR_MODELS,
    SAO_MONTH_MODELS,
    SaoHiepKy,
    ThanSatByYearSao,
    TuDaiCatThoiSao,
)

GOOD = 1
UGLY = 2


def sao_hiep_ky_by_day(hiep_ky_ids):
    """{hiepky_id: [SaoHiepKy, ...]} for every given day, in one query."""
    rows = (
        SaoHiepKy.objects
        .filter(hiepky_id__in=list(hiep_ky_ids))
        .select_related('sao')
        .order_by('id')
    )
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.hiepky_id].append(row)
    return grouped


def star_names(rows, kind):
    """Names of the rows whose star is good (1) or ugly (2)."""
    return [row.sao.name for row in rows if row.sao.good_ugly_stars == kind]


def hiep_ky_star_prefetch():
    """Prefetch a day's stars with their `sao` already joined."""
    return Prefetch(
        'saohiepky_set',
        queryset=SaoHiepKy.objects.select_related('sao').order_by('id'),
    )


def hour_star_prefetches():
    """Prefetches for all twelve hour through-tables of a HourInDay.

    Without the `select_related('sao')` each through row would fetch its star
    separately, which is the bulk of the HourInDay serializer's cost.
    """
    return [
        Prefetch(
            'saohour{}_set'.format(index),
            queryset=model.objects.select_related('sao').order_by('id'),
        )
        for index, model in enumerate(SAO_HOUR_MODELS, start=1)
    ]


def tu_dai_star_prefetch():
    return Prefetch(
        'tudaicatthoisao_set',
        queryset=TuDaiCatThoiSao.objects.select_related('sao').order_by('id'),
    )


def than_sat_year_prefetch():
    """The yearly star set, joined through to `sao` and its category.

    `SaoSerializer` renders `sao.category`, so both hops must be joined or the
    serializer walks them one row at a time.
    """
    return Prefetch(
        'thansatbyyearsao_set',
        queryset=ThanSatByYearSao.objects.select_related('sao', 'sao__category').order_by('id'),
    )


def than_sat_month_prefetches():
    """The twelve monthly star sets, each joined through to `sao.category`."""
    return [
        Prefetch(
            'saomonth{}_set'.format(index),
            queryset=model.objects.select_related('sao', 'sao__category').order_by('id'),
        )
        for index, model in enumerate(SAO_MONTH_MODELS, start=1)
    ]
