from datetime import datetime

from django.contrib import admin
from django_object_actions import action, DjangoObjectActions

from apis.models import Sao, HiepKy, SaoHiepKy, HourInDay, TuDaiCatThoi, QuyNhan, ThanSatByYear, ThanSatByMonth, \
    DateConfig, HoursConfig, BankConfig, BankTransaction, CategoryStars, DirectionConfig

admin.site.site_header = 'Thiên văn lịch pháp'


class SaoAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'good_ugly_stars']
    search_fields = ['name', 'good_ugly_stars']
    list_filter = ['good_ugly_stars', 'is_mountain', 'category']


admin.site.register(Sao, SaoAdmin)


class CategoryStarsAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']


admin.site.register(CategoryStars, CategoryStarsAdmin)


class HiepKySaoGoodAdmin(admin.TabularInline):
    model = HiepKy.sao.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )
    search_fields = ['sao']

    verbose_name = "Sao"
    verbose_name_plural = "Sao"


class HiepKyAdmin(admin.ModelAdmin):
    list_display = ['id', 'month', 'lunar_day']
    search_fields = ['lunar_day', 'month']
    list_filter = ['lunar_day', 'month']

    inlines = [
        HiepKySaoGoodAdmin
    ]


admin.site.register(HiepKy, HiepKyAdmin)


class TyInline(admin.TabularInline):
    model = HourInDay.hour_1.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class SuuInline(admin.TabularInline):
    model = HourInDay.hour_2.through
    extra = 0


class DanInline(admin.TabularInline):
    model = HourInDay.hour_3.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class MaoInline(admin.TabularInline):
    model = HourInDay.hour_4.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class ThinInline(admin.TabularInline):
    model = HourInDay.hour_5.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class TiInline(admin.TabularInline):
    model = HourInDay.hour_6.through
    extra = 0
    autocomplete_fields = (
        'hour_6',
    )


class NgoInline(admin.TabularInline):
    model = HourInDay.hour_7.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class MuiInline(admin.TabularInline):
    model = HourInDay.hour_8.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class ThanInline(admin.TabularInline):
    model = HourInDay.hour_9.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class DauInline(admin.TabularInline):
    model = HourInDay.hour_10.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class TuatInline(admin.TabularInline):
    model = HourInDay.hour_11.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class HoiInline(admin.TabularInline):
    model = HourInDay.hour_12.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class HourInDayAdmin(admin.ModelAdmin):
    list_display = ['id', 'lunar_day']
    search_fields = ['lunar_day']

    inlines = [
        TyInline, SuuInline, DanInline, MaoInline, ThinInline, TiInline, NgoInline, MuiInline, ThanInline, DauInline,
        TuatInline, HoiInline
    ]


admin.site.register(HourInDay, HourInDayAdmin)


class TuDaiCatThoiSaoInline(admin.TabularInline):
    model = TuDaiCatThoi.sao.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


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


class ThanSatInline(admin.TabularInline):
    model = ThanSatByYear.sao.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class ThanSatYearAdmin(admin.ModelAdmin):
    list_display = ['id', 'year']
    search_fields = ['year']

    inlines = [
        ThanSatInline
    ]


admin.site.register(ThanSatByYear, ThanSatYearAdmin)


class Month1Inline(admin.TabularInline):
    model = ThanSatByMonth.month_1.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class Month2Inline(admin.TabularInline):
    model = ThanSatByMonth.month_2.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class Month3Inline(admin.TabularInline):
    model = ThanSatByMonth.month_3.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class Month4Inline(admin.TabularInline):
    model = ThanSatByMonth.month_4.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class Month5Inline(admin.TabularInline):
    model = ThanSatByMonth.month_5.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class Month6Inline(admin.TabularInline):
    model = ThanSatByMonth.month_6.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class Month7Inline(admin.TabularInline):
    model = ThanSatByMonth.month_7.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class Month8Inline(admin.TabularInline):
    model = ThanSatByMonth.month_8.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class Month9Inline(admin.TabularInline):
    model = ThanSatByMonth.month_9.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class Month10Inline(admin.TabularInline):
    model = ThanSatByMonth.month_10.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class Month11Inline(admin.TabularInline):
    model = ThanSatByMonth.month_11.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class Month12Inline(admin.TabularInline):
    model = ThanSatByMonth.month_12.through
    extra = 0
    autocomplete_fields = (
        'sao',
    )


class ThanSatMonthAdmin(admin.ModelAdmin):
    list_display = ['id', 'year']
    search_fields = ['year__year']

    inlines = [
        Month1Inline, Month2Inline, Month3Inline, Month4Inline, Month5Inline, Month6Inline, Month7Inline,
        Month8Inline, Month9Inline, Month10Inline, Month11Inline, Month12Inline
    ]


admin.site.register(ThanSatByMonth, ThanSatMonthAdmin)


class DateConfigAdmin(admin.ModelAdmin):
    list_display = ['id', 'very_good_from', 'good_from', 'ugly_from']


admin.site.register(DateConfig, DateConfigAdmin)


class HoursConfigAdmin(admin.ModelAdmin):
    list_display = ['id', 'very_good', 'good']


admin.site.register(HoursConfig, HoursConfigAdmin)


class BankConfigAdmin(admin.ModelAdmin):
    list_display = ['account_number', 'account_holder', 'bank', 'branch']


admin.site.register(BankConfig, BankConfigAdmin)


# @admin.action(description="Hoàn thành")
# def make_done(modeladmin, request, queryset):
#     queryset.update(status=1)


class BankTransactionAdmin(DjangoObjectActions, admin.ModelAdmin):
    list_display = ['user', 'code', 'status']

    @action(
        label="Hoàn thành",  # optional
        description="This will be the tooltip of the button"  # optional
    )
    def make_done(modeladmin, request, queryset):
        for el in queryset:
            if hasattr('profile', el.user):
                profile = el.user.profile
                profile.is_free = 1
                profile.expiry_datetime = datetime.now()
                profile.save()
        queryset.update(status=1)

    changelist_actions = ('make_done',)


admin.site.register(BankTransaction, BankTransactionAdmin)


class DirectorConfigAdmin(admin.ModelAdmin):
    list_display = ['id', 'value']


admin.site.register(DirectionConfig, DirectorConfigAdmin)