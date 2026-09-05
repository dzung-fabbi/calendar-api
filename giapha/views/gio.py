"""`GET /clans/{clan_id}/lich-gio` -- the clan's death anniversaries over a
solar window.

Query budget is exactly 2 for any clan size: the `IsClanMember` role check
(1, cached on the request) plus the single `deceased_with_lunar_death` query.
Everything after that is arithmetic in `services.gio`.

WHY A WINDOW AND NOT A YEAR
---------------------------
A giỗ recurs on the *lunar* calendar, so it drifts through the solar year and
a person can have two giỗ inside one solar year (a month-11 or month-12
anniversary can land in early January and again in late December). The
endpoint therefore returns occurrences in a window, never "this person's giỗ
this year".
"""

import datetime as dt

from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.permissions import IsClanMember
from giapha.selectors.gio import deceased_with_lunar_death
from giapha.serializers.gio import GioListSerializer
from giapha.services.can_chi import can_chi_for_date
from giapha.services.gio import gio_occurrences_in_range, lunar_years_covering, today_vn
from giapha.services.vn_lunar import MAX_YEAR, MIN_YEAR

# Two years of occurrences for a 5.000-person clan is already ~10.000 rows.
# Longer windows are a report, not an API call. 731 is the largest gap two
# dates exactly two calendar years apart can have (the span containing a leap
# day); 732 would let "2 năm" quietly mean two years and a day.
MAX_WINDOW_DAYS = 731


def _parse_date(request, name):
    """`None` if absent; a `date` if an ISO `YYYY-MM-DD`; 400 otherwise."""
    raw = request.query_params.get(name)
    if raw is None:
        return None
    try:
        return dt.datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        raise BadRequestException(
            'Tham số {} phải có dạng YYYY-MM-DD.'.format(name)
        )


def _one_year_from(start):
    """`start` plus one calendar year, so the default window is genuinely 12
    months rather than 365 days -- across a leap February those differ, and
    the missing day would silently drop a giỗ off the end of the list.
    """
    try:
        return start.replace(year=start.year + 1)
    except ValueError:
        # 29 February: the next year has no such day.
        return start.replace(year=start.year + 1, day=28)


def _parse_window(request):
    """Resolve `?from=&to=` / `?year=` / nothing into a `(start, end)` pair.

    `?year=` is the convenience form for a whole solar year. Omitting
    everything gives the next 12 months from today in Vietnam -- the common
    case, and the one a client opening the screen wants.
    """
    raw_year = request.query_params.get('year')

    if raw_year is not None:
        # Checked against raw presence, before parsing, so `?year=&from=oops`
        # reports the real mistake (combining them) rather than the format.
        if 'from' in request.query_params or 'to' in request.query_params:
            raise BadRequestException('Không dùng year cùng lúc với from/to.')
        try:
            year = int(raw_year)
        except ValueError:
            raise BadRequestException('Tham số year phải là số nguyên.')
        # Range-check BEFORE building any `date`. `dt.date()` raises
        # `ValueError` for year 0 or > 9999 and `OverflowError` for a bignum;
        # DRF's default handler passes neither through as a 400, so an
        # unchecked `?year=0` becomes a 500 with a traceback.
        if not (MIN_YEAR <= year <= MAX_YEAR):
            raise BadRequestException(
                'Chỉ hỗ trợ các năm từ {} đến {}.'.format(MIN_YEAR, MAX_YEAR)
            )
        return dt.date(year, 1, 1), dt.date(year, 12, 31)

    start = _parse_date(request, 'from')
    end = _parse_date(request, 'to')

    if start is None and end is None:
        start = today_vn()
        return start, _one_year_from(start)
    if start is None or end is None:
        raise BadRequestException('Phải truyền cả from và to.')
    return start, end


def _validate_window(start, end):
    if end < start:
        raise BadRequestException('Tham số to phải không sớm hơn from.')
    if (end - start).days > MAX_WINDOW_DAYS:
        raise BadRequestException('Khoảng thời gian tối đa là 2 năm.')
    # The lunar conversion is only trustworthy inside `vn_lunar`'s range, and
    # a wrong giỗ date is worse than a 400.
    if not (MIN_YEAR <= start.year and end.year <= MAX_YEAR):
        raise BadRequestException(
            'Chỉ hỗ trợ các năm từ {} đến {}.'.format(MIN_YEAR, MAX_YEAR)
        )


def _items_for(rows, start, end, today):
    """Flatten `rows` x their occurrences in the window into response dicts.

    `lunar_years_covering` is hoisted out of the loop: it depends only on the
    window, so computing it per person would repeat the same two conversions
    once per row.
    """
    lunar_years = lunar_years_covering(start, end)
    items = []
    for row in rows:
        occurrences = gio_occurrences_in_range(
            row['death_lunar_day'], row['death_lunar_month'],
            start, end, lunar_years=lunar_years,
        )
        for occurrence in occurrences:
            items.append({
                'person_id': row['id'],
                'ho_ten': row['ho_ten'],
                'thuy_hieu': row['thuy_hieu'],
                'generation': row['generation'],
                'lunar': {'day': occurrence.day, 'month': occurrence.month},
                'lunar_year': occurrence.lunar_year,
                'solar_date': occurrence.solar_date,
                'can_chi_ngay': can_chi_for_date(occurrence.solar_date),
                'days_until': (occurrence.solar_date - today).days,
                'adjusted': occurrence.adjusted,
            })
    # Chronological, then stable by person so a clan with several giỗ on the
    # same day renders in a fixed order rather than DB order.
    items.sort(key=lambda item: (item['solar_date'], item['person_id']))
    return items


class ClanGioCalendarAPIView(APIView):
    """`GET`, any clan member. See module docstring for the query budget."""

    permission_classes = [IsAuthenticated, IsClanMember]

    def get(self, request, clan_id):
        start, end = _parse_window(request)
        _validate_window(start, end)

        rows, truncated = deceased_with_lunar_death(
            clan_id, max_persons=settings.MAX_CLAN_PERSONS,
        )
        items = _items_for(rows, start, end, today_vn())

        return Response(
            GioListSerializer({'items': items, 'truncated': truncated}).data
        )
