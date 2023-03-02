from .models import HiepKy, TietKhi
from rest_framework import serializers


class HiepKySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = HiepKy
        fields = ['month', 'lunar_day', 'good_stars', 'ugly_stars', 'should_things', 'no_should_things']


class TietKhiSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = TietKhi
        fields = ['tiet_khi', 'start_time', 'end_time']
