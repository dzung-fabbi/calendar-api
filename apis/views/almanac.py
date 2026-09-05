"""Read endpoints for the day sheet, solar terms and the day's hours."""

from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.models import HiepKy, HourInDay, QuyNhan, TietKhi, TuDaiCatThoi
from apis.selectors.stars import (
    GOOD,
    UGLY,
    hiep_ky_star_prefetch,
    hour_star_prefetches,
    sao_hiep_ky_by_day,
    star_names,
    tu_dai_star_prefetch,
)
from apis.serializers import (
    HiepKySerializer,
    HourInDaySerializer,
    QuyNhanSerializer,
    TietKhiSerializer,
    TuDaiCatThoiSerializer,
)
from apis.views.params import (
    InvalidParam,
    required,
    required_datetime,
    required_int,
    required_json_list,
)

EMPTY_DAY = {
    'should_things': '',
    'no_should_things': '',
    'good_stars': '',
    'ugly_stars': '',
}


class TietkhiAPIView(APIView):
    def get(self, request):
        tiet_khi = TietKhi.objects.filter(
            tiet_khi=required(request, 'tiet_khi'),
            start_time__year=timezone.now().year,
        ).order_by('start_time').first()
        return Response({'data': TietKhiSerializer(tiet_khi, allow_null=True).data})


class CalendarAPIView(APIView):
    """Day summaries for a batch of (month, lunar_day) pairs.

    Resolves the whole batch with two queries instead of three per day.
    """

    def get(self, request):
        arr_data = self._validated_days(request)
        days_by_key, stars_by_day = self._load(arr_data)

        data = []
        for day in arr_data:
            hiep_ky = days_by_key.get(self._key(day['month'], day['lunar_day']))
            if hiep_ky is not None:
                rows = stars_by_day.get(hiep_ky.id, [])
            else:
                hiep_ky, rows = self._fetch_one(day)

            if hiep_ky is None:
                data.append(dict(EMPTY_DAY))
                continue

            data.append({
                'should_things': hiep_ky.should_things,
                'no_should_things': hiep_ky.no_should_things,
                'good_stars': ','.join(star_names(rows, GOOD)),
                'ugly_stars': ','.join(star_names(rows, UGLY)),
            })
        return Response({'data': data})

    @staticmethod
    def _validated_days(request):
        """Each entry must carry a numeric `month` and a `lunar_day`."""
        arr_data = required_json_list(request, 'data')
        for entry in arr_data:
            if not isinstance(entry, dict):
                raise InvalidParam('data', 'mỗi phần tử phải là một object')
            if 'lunar_day' not in entry:
                raise InvalidParam('data', 'thiếu "lunar_day"')
            try:
                int(entry['month'])
            except (KeyError, TypeError, ValueError):
                raise InvalidParam('data', '"month" phải là số nguyên')
        return arr_data

    @staticmethod
    def _fetch_one(day):
        """Resolve a single day the in-memory index missed.

        MySQL's collation matches more loosely than an upper-cased Python key,
        so a request spelled unusually can match a row that the index did not
        key to. Falling back to the database keeps that behaviour; it costs the
        one query the day used to cost anyway, and normal input never gets here.
        """
        hiep_ky = HiepKy.objects.filter(
            month=day['month'], lunar_day=day['lunar_day']
        ).first()
        if hiep_ky is None:
            return None, []
        return hiep_ky, sao_hiep_ky_by_day([hiep_ky.id]).get(hiep_ky.id, [])

    @staticmethod
    def _key(month, lunar_day):
        return int(month), str(lunar_day).upper()

    def _load(self, arr_data):
        """One query for every requested day, one for all of their stars."""
        if not arr_data:
            return {}, {}

        lookup = Q()
        for day in arr_data:
            lookup |= Q(month=day['month'], lunar_day=day['lunar_day'])

        days = list(HiepKy.objects.filter(lookup))
        days_by_key = {self._key(day.month, day.lunar_day): day for day in days}
        stars_by_day = sao_hiep_ky_by_day([day.id for day in days])
        return days_by_key, stars_by_day


class HomeAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        lunar_day = required(request, 'lunar_day')
        tiet_khi_param = required(request, 'tiet_khi')
        month = required_int(request, 'month')
        lunar_date = required_datetime(request, 'lunar_date')

        tiet_khi = TietKhi.objects.filter(
            start_time__lt=lunar_date
        ).order_by('-start_time').first()
        tiet_khi_serializer = TietKhiSerializer(tiet_khi, allow_null=True)

        hour_in_days = HourInDay.objects.prefetch_related(
            *hour_star_prefetches()
        ).filter(lunar_day=lunar_day).first()
        hour_in_days = HourInDaySerializer(hour_in_days, allow_null=True)

        quy_nhan_data = QuyNhan.objects.filter(
            can_ngay=lunar_day.split()[0], tiet_khi__icontains=tiet_khi_param
        )
        quy_nhan_data = QuyNhanSerializer(quy_nhan_data, many=True)

        tu_dai_data = TuDaiCatThoi.objects.prefetch_related(
            tu_dai_star_prefetch()
        ).filter(tiet_khi__icontains=tiet_khi_param)
        tu_dai_data = TuDaiCatThoiSerializer(tu_dai_data, many=True)

        data = HiepKy.objects.prefetch_related(hiep_ky_star_prefetch()).filter(
            month=month, lunar_day=lunar_day
        ).first()
        serializer = HiepKySerializer(data, allow_null=True)

        return Response({'data': {
            'hiep_ky': serializer.data,
            'tiet_khi': tiet_khi_serializer.data,
            'hour_in_days': hour_in_days.data,
            'quy_nhan': quy_nhan_data.data,
            'tu_dai': tu_dai_data.data
        }})
