from django.contrib import admin
from django.forms import BaseInlineFormSet

from apis.models import Sao, HiepKy, SaoHiepKy, HourInDay, TuDaiCatThoi

admin.site.site_header = 'Thiên văn lịch pháp'


class SaoAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'good_ugly_stars']
    search_fields = ['name', 'good_ugly_stars']
    list_filter = ['good_ugly_stars', 'is_mountain']


admin.site.register(Sao, SaoAdmin)


class DirectorInline(admin.TabularInline):
    model = HiepKy.sao.through
    extra = 0


class HiepKyAdmin(admin.ModelAdmin):
    list_display = ['id', 'month', 'lunar_day']
    search_fields = ['lunar_day', 'month']
    list_filter = ['lunar_day', 'month']
    inlines = [
        DirectorInline,
    ]


admin.site.register(HiepKy, HiepKyAdmin)


class TyInline(admin.TabularInline):
    model = HourInDay.hour_1.through
    extra = 0


class SuuInline(admin.TabularInline):
    model = HourInDay.hour_1.through
    extra = 0


class DanInline(admin.TabularInline):
    model = HourInDay.hour_1.through
    extra = 0


class MaoInline(admin.TabularInline):
    model = HourInDay.hour_1.through
    extra = 0


class ThinInline(admin.TabularInline):
    model = HourInDay.hour_1.through
    extra = 0


class TiInline(admin.TabularInline):
    model = HourInDay.hour_1.through
    extra = 0


class NgoInline(admin.TabularInline):
    model = HourInDay.hour_1.through
    extra = 0


class MuiInline(admin.TabularInline):
    model = HourInDay.hour_1.through
    extra = 0


class ThanInline(admin.TabularInline):
    model = HourInDay.hour_1.through
    extra = 0


class DauInline(admin.TabularInline):
    model = HourInDay.hour_1.through
    extra = 0


class TuatInline(admin.TabularInline):
    model = HourInDay.hour_1.through
    extra = 0


class HoiInline(admin.TabularInline):
    model = HourInDay.hour_1.through
    extra = 0


class HourInDayAdmin(admin.ModelAdmin):
    list_display = ['id', 'lunar_day']

    inlines = [
        TyInline, SuuInline, DanInline, MaoInline, ThinInline, TiInline, NgoInline, MuiInline, ThanInline, DauInline,
        TuatInline, HoiInline
    ]


admin.site.register(HourInDay, HourInDayAdmin)


class TuDaiCatThoiSaoInline(admin.TabularInline):
    model = TuDaiCatThoi.sao.through
    extra = 0


class TuDaiDayAdmin(admin.ModelAdmin):
    list_display = ['id', 'can_ngay', 'tiet_khi']

    inlines = [
        TuDaiCatThoiSaoInline
    ]


admin.site.register(TuDaiCatThoi, TuDaiDayAdmin)
