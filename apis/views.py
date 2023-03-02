from .models import HiepKy
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import HiepKySerializer
from .exceptions import BadRequestException


class TestAPIView(APIView):
    def get(self, request):
        try:
            data = HiepKy.objects.get(month=request.GET.get('month'), lunar_day=request.GET.get('lunar_day'))
            serializer = HiepKySerializer(data)
            return Response({'data': serializer.data})
        except HiepKy.DoesNotExist:
            raise BadRequestException()
