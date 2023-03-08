from .models import HiepKy, TietKhi, HourInDay, QuyNhan, TuDaiCatThoi
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import HiepKySerializer, TietKhiSerializer, HourInDaySerializer, TuDaiCatThoiSerializer, \
    QuyNhanSerializer
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
            tiet_khi_serializer = TietKhiSerializer(tiet_khi, allow_null=True)
            hour_in_days = HourInDay.objects.filter(lunar_day=request.GET.get('lunar_day')).first()
            hour_in_days = HourInDaySerializer(hour_in_days, allow_null=True)
            quy_nhan_data = QuyNhan.objects.filter(
                can_ngay=request.GET.get('lunar_day').split()[0], tiet_khi__icontains=request.GET.get('tiet_khi')
            )
            quy_nhan_data = QuyNhanSerializer(quy_nhan_data, many=True)
            tu_dai_data = TuDaiCatThoi.objects.filter(tiet_khi__icontains=request.GET.get('tiet_khi'))
            tu_dai_data = TuDaiCatThoiSerializer(tu_dai_data, many=True)
            data = HiepKy.objects.filter(
                month=request.GET.get('month'), lunar_day=request.GET.get('lunar_day')
            ).first()
            serializer = HiepKySerializer(data, allow_null=True)
            return Response({'data': {
                'hiep_ky': serializer.data,
                'tiet_khi': tiet_khi_serializer.data,
                'hour_in_days': hour_in_days.data,
                'quy_nhan': quy_nhan_data.data,
                'tu_dai': tu_dai_data.data
            }})
        except Exception:
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
