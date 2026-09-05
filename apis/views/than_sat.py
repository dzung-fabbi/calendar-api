"""Yearly and monthly thần sát endpoint."""

from rest_framework.response import Response
from rest_framework.views import APIView

from apis.models import ThanSatByMonth, ThanSatByYear
from apis.selectors.stars import than_sat_month_prefetches, than_sat_year_prefetch
from apis.serializers import ThanSatByMonthSerializer, ThanSatByYearSerializer


class ThanSatAPIView(APIView):
    def get(self, request):
        year = request.GET.get('year', None)

        than_sat_by_year = ThanSatByYear.objects.prefetch_related(
            than_sat_year_prefetch()
        ).filter(year__iexact=year).first()

        than_sat_by_month = ThanSatByMonth.objects.prefetch_related(
            *than_sat_month_prefetches()
        ).filter(year__year__iexact=year).first()

        return Response(data={
            'than_sat_by_year': ThanSatByYearSerializer(than_sat_by_year, many=False).data,
            'than_sat_by_month': ThanSatByMonthSerializer(than_sat_by_month, many=False).data,
        })
