from .models import *
from rest_framework import serializers


class HiepKySerializer(serializers.HyperlinkedModelSerializer):
    good_stars = serializers.SerializerMethodField()
    ugly_stars = serializers.SerializerMethodField()

    class Meta:
        model = HiepKy
        fields = ['month', 'lunar_day', 'good_stars', 'ugly_stars', 'should_things', 'no_should_things']

    def get_good_stars(self, obj):
        good_stars = SaoHiepKy.objects.filter(sao__good_ugly_stars=1, hiepky=obj)
        tmp = []
        for el in good_stars:
            tmp.append({
                "name": el.sao.name,
                "property": el.sao.property
            })
        return tmp

    def get_ugly_stars(self, obj):
        ugly_stars = SaoHiepKy.objects.filter(sao__good_ugly_stars=2, hiepky=obj)
        tmp = []
        for el in ugly_stars:
            tmp.append({
                "name": el.sao.name,
                "property": el.sao.property
            })
        return tmp


class TietKhiSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = TietKhi
        fields = ['tiet_khi', 'start_time', 'end_time']


class HourInDaySerializer(serializers.HyperlinkedModelSerializer):
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
        stars = SaoHour1.objects.filter(hour_1=obj)
        tmp = []
        for el in stars:
            tmp.append({
                "name": el.sao.name,
                "property": el.sao.property,
                "good_ugly_stars": el.sao.good_ugly_stars
            })
        return tmp

    def get_hour_2(self, obj):
        stars = SaoHour2.objects.filter(hour_2=obj)
        tmp = []
        for el in stars:
            tmp.append({
                "name": el.sao.name,
                "property": el.sao.property,
                "good_ugly_stars": el.sao.good_ugly_stars
            })
        return tmp

    def get_hour_3(self, obj):
        stars = SaoHour3.objects.filter(hour_3=obj)
        tmp = []
        for el in stars:
            tmp.append({
                "name": el.sao.name,
                "property": el.sao.property,
                "good_ugly_stars": el.sao.good_ugly_stars
            })
        return tmp

    def get_hour_4(self, obj):
        stars = SaoHour4.objects.filter(hour_4=obj)
        tmp = []
        for el in stars:
            tmp.append({
                "name": el.sao.name,
                "property": el.sao.property,
                "good_ugly_stars": el.sao.good_ugly_stars
            })
        return tmp

    def get_hour_5(self, obj):
        stars = SaoHour5.objects.filter(hour_5=obj)
        tmp = []
        for el in stars:
            tmp.append({
                "name": el.sao.name,
                "property": el.sao.property,
                "good_ugly_stars": el.sao.good_ugly_stars
            })
        return tmp

    def get_hour_6(self, obj):
        stars = SaoHour6.objects.filter(hour_6=obj)
        tmp = []
        for el in stars:
            tmp.append({
                "name": el.sao.name,
                "property": el.sao.property,
                "good_ugly_stars": el.sao.good_ugly_stars
            })
        return tmp

    def get_hour_7(self, obj):
        stars = SaoHour7.objects.filter(hour_7=obj)
        tmp = []
        for el in stars:
            tmp.append({
                "name": el.sao.name,
                "property": el.sao.property,
                "good_ugly_stars": el.sao.good_ugly_stars
            })
        return tmp

    def get_hour_8(self, obj):
        stars = SaoHour8.objects.filter(hour_8=obj)
        tmp = []
        for el in stars:
            tmp.append({
                "name": el.sao.name,
                "property": el.sao.property,
                "good_ugly_stars": el.sao.good_ugly_stars
            })
        return tmp

    def get_hour_9(self, obj):
        stars = SaoHour9.objects.filter(hour_9=obj)
        tmp = []
        for el in stars:
            tmp.append({
                "name": el.sao.name,
                "property": el.sao.property,
                "good_ugly_stars": el.sao.good_ugly_stars
            })
        return tmp

    def get_hour_10(self, obj):
        stars = SaoHour10.objects.filter(hour_10=obj)
        tmp = []
        for el in stars:
            tmp.append({
                "name": el.sao.name,
                "property": el.sao.property,
                "good_ugly_stars": el.sao.good_ugly_stars
            })
        return tmp

    def get_hour_11(self, obj):
        stars = SaoHour11.objects.filter(hour_11=obj)
        tmp = []
        for el in stars:
            tmp.append({
                "name": el.sao.name,
                "property": el.sao.property,
                "good_ugly_stars": el.sao.good_ugly_stars
            })
        return tmp

    def get_hour_12(self, obj):
        stars = SaoHour12.objects.filter(hour_12=obj)
        tmp = []
        for el in stars:
            tmp.append({
                "name": el.sao.name,
                "property": el.sao.property,
                "good_ugly_stars": el.sao.good_ugly_stars
            })
        return tmp


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
        stars = TuDaiCatThoiSao.objects.filter(tudaicatthoi=obj)
        tmp = []
        for el in stars:
            tmp.append({
                "name": el.sao.name,
                "property": el.sao.property,
                "good_ugly_stars": el.sao.good_ugly_stars
            })
        return tmp


class SaoSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()

    class Meta:
        model = Sao
        fields = [
            'id',
            'name',
            'property',
            'good_ugly_stars',
            'is_mountain',
            'category',
        ]

    def get_category(self, obj):
        if obj.category is None:
            return None
        result = {
            "id": obj.category.id,
            "name": obj.category.name,
        }
        return result


class ThanSatYearSaoSerializer(serializers.ModelSerializer):
    sao = SaoSerializer(read_only=True)

    class Meta:
        model = ThanSatByYearSao
        fields = ['cung_son', 'sao', 'direction']


class ThanSatByYearSerializer(serializers.ModelSerializer):
    than_sat_sao = ThanSatYearSaoSerializer(source='thansatbyyearsao_set', read_only=True, many=True)

    class Meta:
        model = ThanSatByYear
        fields = ['year', 'than_sat_sao']


class SaoMonth1Serializer(serializers.ModelSerializer):
    sao = SaoSerializer(read_only=True)

    class Meta:
        model = SaoMonth1
        fields = ['cung_son', 'sao', 'direction']


class SaoMonth2Serializer(serializers.ModelSerializer):
    sao = SaoSerializer(read_only=True)

    class Meta:
        model = SaoMonth2
        fields = ['cung_son', 'sao', 'direction']


class SaoMonth3Serializer(serializers.ModelSerializer):
    sao = SaoSerializer(read_only=True)

    class Meta:
        model = SaoMonth3
        fields = ['cung_son', 'sao', 'direction']


class SaoMonth4Serializer(serializers.ModelSerializer):
    sao = SaoSerializer(read_only=True)

    class Meta:
        model = SaoMonth4
        fields = ['cung_son', 'sao', 'direction']


class SaoMonth5Serializer(serializers.ModelSerializer):
    sao = SaoSerializer(read_only=True)

    class Meta:
        model = SaoMonth5
        fields = ['cung_son', 'sao', 'direction']


class SaoMonth6Serializer(serializers.ModelSerializer):
    sao = SaoSerializer(read_only=True)

    class Meta:
        model = SaoMonth6
        fields = ['cung_son', 'sao', 'direction']


class SaoMonth7Serializer(serializers.ModelSerializer):
    sao = SaoSerializer(read_only=True)

    class Meta:
        model = SaoMonth7
        fields = ['cung_son', 'sao', 'direction']


class SaoMonth8Serializer(serializers.ModelSerializer):
    sao = SaoSerializer(read_only=True)

    class Meta:
        model = SaoMonth8
        fields = ['cung_son', 'sao', 'direction']


class SaoMonth9Serializer(serializers.ModelSerializer):
    sao = SaoSerializer(read_only=True)

    class Meta:
        model = SaoMonth9
        fields = ['cung_son', 'sao', 'direction']


class SaoMonth10Serializer(serializers.ModelSerializer):
    sao = SaoSerializer(read_only=True)

    class Meta:
        model = SaoMonth10
        fields = ['cung_son', 'sao', 'direction']


class SaoMonth11Serializer(serializers.ModelSerializer):
    sao = SaoSerializer(read_only=True)

    class Meta:
        model = SaoMonth11
        fields = ['cung_son', 'sao', 'direction']


class SaoMonth12Serializer(serializers.ModelSerializer):
    sao = SaoSerializer(read_only=True)

    class Meta:
        model = SaoMonth12
        fields = ['cung_son', 'sao', 'direction']


class ThanSatByMonthSerializer(serializers.ModelSerializer):
    month_01 = SaoMonth1Serializer(source='saomonth1_set', read_only=True, many=True)
    month_02 = SaoMonth1Serializer(source='saomonth2_set', read_only=True, many=True)
    month_03 = SaoMonth1Serializer(source='saomonth3_set', read_only=True, many=True)
    month_04 = SaoMonth1Serializer(source='saomonth4_set', read_only=True, many=True)
    month_05 = SaoMonth1Serializer(source='saomonth5_set', read_only=True, many=True)
    month_06 = SaoMonth1Serializer(source='saomonth6_set', read_only=True, many=True)
    month_07 = SaoMonth1Serializer(source='saomonth7_set', read_only=True, many=True)
    month_08 = SaoMonth1Serializer(source='saomonth8_set', read_only=True, many=True)
    month_09 = SaoMonth1Serializer(source='saomonth9_set', read_only=True, many=True)
    month_10 = SaoMonth1Serializer(source='saomonth10_set', read_only=True, many=True)
    month_11 = SaoMonth1Serializer(source='saomonth11_set', read_only=True, many=True)
    month_12 = SaoMonth1Serializer(source='saomonth12_set', read_only=True, many=True)

    class Meta:
        model = ThanSatByMonth
        fields = [
            'month_01',
            'month_02',
            'month_03',
            'month_04',
            'month_05',
            'month_06',
            'month_07',
            'month_08',
            'month_09',
            'month_10',
            'month_11',
            'month_12',
        ]


class BookCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookCalendar
        fields = ['work', 'date', 'email']


class AppointmentDateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppointmentDate
        fields = ('id', 'name', 'date', 'user_id')


class DateConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = DateConfig
        fields = '__all__'


class HoursConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = HoursConfig
        fields = '__all__'


class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankConfig
        fields = '__all__'