"""Site configuration and the authenticated user's own record."""

from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.models import DateConfig, DirectionConfig, HoursConfig
from apis.serializers import (
    DateConfigSerializer,
    DirectionConfigSerializer,
    HoursConfigSerializer,
    UserSerializer,
)


class ConfigAPIView(APIView):
    def get(self, request):
        date_config = DateConfig.objects.order_by('-id').first()
        hours_config = HoursConfig.objects.order_by('-id').first()
        direction_config = DirectionConfig.objects.order_by('-id').first()
        return Response({'data': {
            'date_config': DateConfigSerializer(date_config, many=False).data,
            'hours_config': HoursConfigSerializer(hours_config, many=False).data,
            'direction_config': DirectionConfigSerializer(direction_config, many=False).data,
        }})


class UserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = User.objects.get(id=request.user.id)
        serializer = UserSerializer(data)
        return Response({'data': serializer.data})
