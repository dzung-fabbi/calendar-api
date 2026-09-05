"""Serializers for the day sheet, solar terms and the day's twelve hours."""

from rest_framework import serializers

from apis.models import HiepKy, HourInDay, QuyNhan, TietKhi, TuDaiCatThoi
from apis.serializers.stars import named_star_payload, star_payload


class HiepKySerializer(serializers.HyperlinkedModelSerializer):
    good_stars = serializers.SerializerMethodField()
    ugly_stars = serializers.SerializerMethodField()

    class Meta:
        model = HiepKy
        fields = ['month', 'lunar_day', 'good_stars', 'ugly_stars', 'should_things', 'no_should_things']

    def get_good_stars(self, obj):
        return named_star_payload(self._rows_by_kind(obj, kind=1))

    def get_ugly_stars(self, obj):
        return named_star_payload(self._rows_by_kind(obj, kind=2))

    @staticmethod
    def _rows_by_kind(obj, kind):
        """Split the day's stars in memory.

        Filtering the prefetched rows rather than issuing one query per kind
        keeps this at zero queries when the caller prefetched
        `saohiepky_set` with `select_related('sao')`.
        """
        return [row for row in obj.saohiepky_set.all() if row.sao.good_ugly_stars == kind]


class TietKhiSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = TietKhi
        fields = ['tiet_khi', 'start_time', 'end_time']


class HourInDaySerializer(serializers.HyperlinkedModelSerializer):
    """The twelve hours of a day, each carrying its stars.

    Every `get_hour_N` reads the matching reverse accessor so a caller that
    prefetches `saohourN_set` pays no extra queries.
    """

    hour_1 = serializers.SerializerMethodField()
    hour_2 = serializers.SerializerMethodField()
    hour_3 = serializers.SerializerMethodField()
    hour_4 = serializers.SerializerMethodField()
    hour_5 = serializers.SerializerMethodField()
    hour_6 = serializers.SerializerMethodField()
    hour_7 = serializers.SerializerMethodField()
    hour_8 = serializers.SerializerMethodField()
    hour_9 = serializers.SerializerMethodField()
    hour_10 = serializers.SerializerMethodField()
    hour_11 = serializers.SerializerMethodField()
    hour_12 = serializers.SerializerMethodField()

    class Meta:
        model = HourInDay
        fields = ['lunar_day', 'hour_1', 'hour_2', 'hour_3', 'hour_4', 'hour_5',
                  'hour_6', 'hour_7', 'hour_8', 'hour_9', 'hour_10', 'hour_11', 'hour_12']

    def get_hour_1(self, obj):
        return star_payload(obj.saohour1_set.all())

    def get_hour_2(self, obj):
        return star_payload(obj.saohour2_set.all())

    def get_hour_3(self, obj):
        return star_payload(obj.saohour3_set.all())

    def get_hour_4(self, obj):
        return star_payload(obj.saohour4_set.all())

    def get_hour_5(self, obj):
        return star_payload(obj.saohour5_set.all())

    def get_hour_6(self, obj):
        return star_payload(obj.saohour6_set.all())

    def get_hour_7(self, obj):
        return star_payload(obj.saohour7_set.all())

    def get_hour_8(self, obj):
        return star_payload(obj.saohour8_set.all())

    def get_hour_9(self, obj):
        return star_payload(obj.saohour9_set.all())

    def get_hour_10(self, obj):
        return star_payload(obj.saohour10_set.all())

    def get_hour_11(self, obj):
        return star_payload(obj.saohour11_set.all())

    def get_hour_12(self, obj):
        return star_payload(obj.saohour12_set.all())


class QuyNhanSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = QuyNhan
        fields = ['can_ngay', 'tiet_khi', 'hour', 'am_duong', 'quy_nhan']


class TuDaiCatThoiSerializer(serializers.HyperlinkedModelSerializer):
    sao = serializers.SerializerMethodField()

    class Meta:
        model = TuDaiCatThoi
        fields = ['hour', 'can_ngay', 'sao', 'tiet_khi']

    def get_sao(self, obj):
        return star_payload(obj.tudaicatthoisao_set.all())
