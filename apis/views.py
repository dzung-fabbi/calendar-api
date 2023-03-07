from .models import HiepKy, TietKhi, HourInDay
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import HiepKySerializer, TietKhiSerializer, HourInDaySerializer
from .exceptions import BadRequestException
from datetime import datetime
from itertools import chain
from operator import attrgetter


class HomeAPIView(APIView):
    def get(self, request):
        tiet_khi = None
        try:
            tiet_khi = TietKhi.objects.filter(start_time__lt=request.GET.get('lunar_date')).order_by(
                '-start_time'
            ).first()
            tiet_khi_serializer = TietKhiSerializer(tiet_khi)
            hour_in_days = HourInDay.objects.filter(lunar_day=request.GET.get('lunar_day')).first()
            hour_in_days = HourInDaySerializer(hour_in_days)
            data = HiepKy.objects.get(month=request.GET.get('month'), lunar_day=request.GET.get('lunar_day'))
            serializer = HiepKySerializer(data)
            return Response({'data': {
                'hiep_ky': serializer.data,
                'tiet_khi': tiet_khi_serializer.data,
                'hour_in_days': hour_in_days.data
            }})
        except Exception:
            if tiet_khi:
                return Response({'data': {
                    'hiep_ky': {
                        'month': '',
                        'good_stars': '',
                        'ugly_stars': '',
                        'should_things': '',
                        'no_should_things': '',
                    },
                    'tiet_khi': tiet_khi_serializer.data,
                    'hour_in_days': hour_in_days.data
                }})
            raise BadRequestException()


class TietkhiAPIView(APIView):
    def get(self, request):
        try:
            tiet_khi_less = TietKhi.objects.filter(
                tiet_khi=request.GET.get('tiet_khi'),
                start_time__lt=datetime.now()
            ).order_by('-start_time')[:5]
            tiet_khi_great = TietKhi.objects.filter(
                tiet_khi=request.GET.get('tiet_khi'),
                start_time__gte=datetime.now()
            ).order_by('start_time')[:5]
            serializer = TietKhiSerializer(sorted(
                chain(tiet_khi_less, tiet_khi_great), key=attrgetter('start_time')
            ), many=True)
            return Response({'data': serializer.data})
        except Exception:
            raise BadRequestException()
