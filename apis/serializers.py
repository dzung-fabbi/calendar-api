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
    class Meta:
        model = TuDaiCatThoi
        fields = ['hour', 'can_ngay_1', 'can_ngay_2', 'can_ngay_3', 'can_ngay_4', 'can_ngay_5',
                  'can_ngay_6', 'can_ngay_7', 'can_ngay_8', 'can_ngay_9', 'can_ngay_10', 'tiet_khi']


class KhaiSonTuPhuongCatSerializer(serializers.ModelSerializer):
    class Meta:
        model = KhaiSonTuPhuongCat
        fields = '__all__'


class TamNguyenTuBachSerializer(serializers.ModelSerializer):
    class Meta:
        model = TamNguyenTuBach
        fields = '__all__'


class CaiSonHoangDaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaiSonHoangDao
        fields = '__all__'


class ThongThienKhieuSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThongThienKhieu
        fields = '__all__'


class TauMaLucNhamSerializer(serializers.ModelSerializer):
    class Meta:
        model = TauMaLucNham
        fields = '__all__'


class KhaiSonTuPhuongHungSerializer(serializers.ModelSerializer):
    class Meta:
        model = KhaiSonTuPhuongHung
        fields = '__all__'


class KhaiSonHungSerializer(serializers.ModelSerializer):
    class Meta:
        model = KhaiSonHung
        fields = '__all__'

class AmPhuThaiTueSerializer(serializers.ModelSerializer):
    class Meta:
        model = AmPhuThaiTue
        fields = '__all__'

class LapHuongHungSerializer(serializers.ModelSerializer):
    class Meta:
        model = LapHuongHung
        fields = '__all__'


class TuPhuongHungSerializer(serializers.ModelSerializer):
    class Meta:
        model = TuPhuongHung
        fields = '__all__'

class LapHuongHungThangSerializer(serializers.ModelSerializer):
    class Meta:
        model = LapHuongHungThang
        fields = '__all__'
class KhaiSonHungThangSerializer(serializers.ModelSerializer):
    class Meta:
        model = KhaiSonHungThang
        fields = '__all__'
class TuPhuongHungThangSerializer(serializers.ModelSerializer):
    class Meta:
        model = TuPhuongHungThang
        fields = '__all__'

class TamKyThangSerializer(serializers.ModelSerializer):
    class Meta:
        model = TamKyThang
        fields = '__all__'


