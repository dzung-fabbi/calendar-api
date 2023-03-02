from .models import HiepKy, TietKhi
from rest_framework import serializers


class HiepKySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = HiepKy
        fields = ['month', 'lunar_day', 'good_stars', 'ugly_stars', 'should_things', 'no_should_things']
