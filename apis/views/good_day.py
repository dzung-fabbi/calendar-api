"""Finding the auspicious days of a lunar month for a given kind of work."""

from rest_framework.response import Response
from rest_framework.views import APIView

from apis.models import DateConfig, HiepKy
from apis.selectors.stars import GOOD, UGLY, sao_hiep_ky_by_day, star_names
from apis.services.can_chi import (
    can_chi_index_for_lunar_month,
    solar_date_to_lunar_string,
)
from apis.services.day_rating import config_from, rate_day
from apis.views.params import required_int

WORK_ALIASES = {
    'Tu tạo mồ mả': 'Tu Tạo Động Thổ',
}


class DateGoodByWorkAPIView(APIView):
    def get(self, request):
        work = request.GET.get('work', '')
        work = WORK_ALIASES.get(work, work)
        month = required_int(request, 'month')
        year = required_int(request, 'year')

        hiep_ky = list(HiepKy.objects.filter(should_things__icontains=work, month=month))
        stars_by_day = sao_hiep_ky_by_day([day.id for day in hiep_ky])

        # The solar date of every can-chi in this lunar month, computed once.
        # This used to be recomputed -- a full month of calendar conversions --
        # for every candidate day.
        can_chi_index = can_chi_index_for_lunar_month(year, month)

        # Thresholds and weights are admin-editable; they used to be constants
        # in this method, leaving the DateConfig screen with no effect.
        config = config_from(DateConfig.objects.order_by('-id').first())

        data = []
        for el in hiep_ky:
            rows = stars_by_day.get(el.id, [])
            is_good = rate_day(
                el.should_things,
                el.no_should_things,
                ','.join(star_names(rows, GOOD)),
                ','.join(star_names(rows, UGLY)),
                config,
            )
            if not is_good["is_good"]:
                continue

            solar_date = can_chi_index.get(el.lunar_day.upper())
            if solar_date is None:
                continue

            data.append({
                "month": el.month,
                "work": el.should_things,
                "lunar_day": el.lunar_day,
                "lunar_date": solar_date_to_lunar_string(solar_date),
                "percent": is_good['percent'],
                "text": is_good['text'],
            })

        data = sorted(data, key=lambda x: x['percent'], reverse=True)
        return Response({'data': data})
