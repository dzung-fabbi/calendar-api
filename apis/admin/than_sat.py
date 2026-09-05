"""Admin for the yearly and monthly thần sát tables."""

from django.contrib import admin

from apis.admin.inlines import through_inline, through_inlines
from apis.models import SAO_MONTH_MODELS, ThanSatByMonth, ThanSatByYear


@admin.register(ThanSatByYear)
class ThanSatYearAdmin(admin.ModelAdmin):
    list_display = ['id', 'year']
    search_fields = ['year']
    inlines = [through_inline(ThanSatByYear.sao.through)]


@admin.register(ThanSatByMonth)
class ThanSatMonthAdmin(admin.ModelAdmin):
    list_display = ['id', 'year']
    search_fields = ['year__year']
    list_select_related = ['year']
    inlines = through_inlines(SAO_MONTH_MODELS, label="Sao tháng")
