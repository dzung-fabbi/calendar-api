from django.contrib import admin
from django.forms import BaseInlineFormSet

from apis.models import Sao, HiepKy, SaoHiepKy, HourInDay, TuDaiCatThoi, QuyNhan

admin.site.site_header = 'Thiên văn lịch pháp'


class SaoAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'good_ugly_stars']
    search_fields = ['name', 'good_ugly_stars']
    list_filter = ['good_ugly_stars', 'is_mountain']


admin.site.register(Sao, SaoAdmin)


class HiepKySaoGoodAdmin(admin.TabularInline):
    model = HiepKy.sao.through
    extra = 0

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(sao__good_ugly_stars=1)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "sao":
            kwargs["queryset"] = Sao.objects.filter(good_ugly_stars=1)
        return super(HiepKySaoGoodAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    verbose_name = "Sao Tốt"
    verbose_name_plural = "Sao Tốt"


class HiepKySaoUglyAdmin(admin.TabularInline):
    model = HiepKy.sao.through
    extra = 0

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(sao__good_ugly_stars=2)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "sao":
            kwargs["queryset"] = Sao.objects.filter(good_ugly_stars=2)
        return super(HiepKySaoUglyAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    verbose_name = "Sao Xấu"
    verbose_name_plural = "Sao Xấu"


class HiepKySaoNoConfirmAdmin(admin.TabularInline):
    model = HiepKy.sao.through
    extra = 0

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(sao__good_ugly_stars=0)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "sao":
            kwargs["queryset"] = Sao.objects.filter(good_ugly_stars=0)
        return super(HiepKySaoNoConfirmAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    verbose_name = "Sao không xác định"
    verbose_name_plural = "Sao không xác đinh"


class HiepKyAdmin(admin.ModelAdmin):
    list_display = ['id', 'month', 'lunar_day']
    search_fields = ['lunar_day', 'month']
    list_filter = ['lunar_day', 'month']
    inlines = [
        HiepKySaoGoodAdmin, HiepKySaoUglyAdmin, HiepKySaoNoConfirmAdmin
    ]


admin.site.register(HiepKy, HiepKyAdmin)


class TyInline(admin.TabularInline):
    model = HourInDay.hour_1.through
    extra = 0


class SuuInline(admin.TabularInline):
    model = HourInDay.hour_2.through
    extra = 0


class DanInline(admin.TabularInline):
    model = HourInDay.hour_3.through
    extra = 0


class MaoInline(admin.TabularInline):
    model = HourInDay.hour_4.through
    extra = 0


class ThinInline(admin.TabularInline):
    model = HourInDay.hour_5.through
    extra = 0


class TiInline(admin.TabularInline):
    model = HourInDay.hour_6.through
    extra = 0


class NgoInline(admin.TabularInline):
    model = HourInDay.hour_7.through
    extra = 0


class MuiInline(admin.TabularInline):
    model = HourInDay.hour_8.through
    extra = 0


class ThanInline(admin.TabularInline):
    model = HourInDay.hour_9.through
    extra = 0


class DauInline(admin.TabularInline):
    model = HourInDay.hour_10.through
    extra = 0


class TuatInline(admin.TabularInline):
    model = HourInDay.hour_11.through
    extra = 0


class HoiInline(admin.TabularInline):
    model = HourInDay.hour_12.through
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
    list_filter = ['can_ngay', 'tiet_khi']

    inlines = [
        TuDaiCatThoiSaoInline
    ]


admin.site.register(TuDaiCatThoi, TuDaiDayAdmin)


class QuyNhanAdmin(admin.ModelAdmin):
    list_display = ['id', 'can_ngay', 'tiet_khi', 'am_duong', 'quy_nhan']
    list_filter = ['can_ngay', 'tiet_khi']


admin.site.register(QuyNhan, QuyNhanAdmin)
