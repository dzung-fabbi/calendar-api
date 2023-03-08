from .models import HiepKy, TietKhi, HourInDay, QuyNhan, TuDaiCatThoi
from rest_framework import serializers


class HiepKySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = HiepKy
        fields = ['month', 'lunar_day', 'good_stars', 'ugly_stars', 'should_things', 'no_should_things']


class TietKhiSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = TietKhi
        fields = ['tiet_khi', 'start_time', 'end_time']


class HourInDaySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = HourInDay
        fields = ['lunar_day', 'hour_1', 'hour_2', 'hour_3', 'hour_4', 'hour_5',
                  'hour_6', 'hour_7', 'hour_8', 'hour_9', 'hour_10', 'hour_11', 'hour_12']


class QuyNhanSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = QuyNhan
        fields = ['can_ngay', 'tiet_khi', 'hour', 'am_duong', 'quy_nhan']


class TuDaiCatThoiSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = TuDaiCatThoi
        fields = ['hour', 'can_ngay_1', 'can_ngay_2', 'can_ngay_3', 'can_ngay_4', 'can_ngay_5',
                  'can_ngay_6', 'can_ngay_7', 'can_ngay_8', 'can_ngay_9', 'can_ngay_10', 'tiet_khi']
