from .models import HiepKy, TietKhi
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import HiepKySerializer, TietKhiSerializer
from .exceptions import BadRequestException


class TestAPIView(APIView):
    def get(self, request):
        try:
            data = HiepKy.objects.get(month=request.GET.get('month'), lunar_day=request.GET.get('lunar_day'))
            serializer = HiepKySerializer(data)
            tiet_khi = TietKhi.objects.filter(start_time__lt=request.GET.get('lunar_date')).order_by(
                '-start_time'
            ).first()
            tiet_khi_serializer = TietKhiSerializer(tiet_khi)
            return Response({'data': {
                'hiep_ky': serializer.data,
                'tiet_khi': tiet_khi_serializer.data
            }})
        except Exception:
            raise BadRequestException()
