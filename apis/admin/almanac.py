"""Admin for the star catalogue, the day sheet and the day's hours."""

from django.contrib import admin

from apis.admin.inlines import through_inline
from apis.models import (
    SAO_HOUR_MODELS,
    CategoryStars,
    HiepKy,
    HourInDay,
    QuyNhan,
    Sao,
    TuDaiCatThoi,
)

# The twelve hours of the day, in order, as they are labelled in the UI.
HOUR_LABELS = [
    "Giờ tý", "Giờ sửu", "Giờ dần", "Giờ mão", "Giờ thìn", "Giờ tỵ",
    "Giờ ngọ", "Giờ mùi", "Giờ thân", "Giờ dậu", "Giờ tuất", "Giờ hợi",
]


@admin.register(Sao)
class SaoAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'good_ugly_stars']
    search_fields = ['name', 'good_ugly_stars']
    list_filter = ['good_ugly_stars', 'is_mountain', 'category']
    list_select_related = ['category']


@admin.register(CategoryStars)
class CategoryStarsAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']
    search_fields = ['name']


@admin.register(HiepKy)
class HiepKyAdmin(admin.ModelAdmin):
    list_display = ['id', 'month', 'lunar_day']
    search_fields = ['lunar_day', 'month']
    list_filter = ['lunar_day', 'month']
    inlines = [through_inline(HiepKy.sao.through, verbose_name="Sao")]


@admin.register(HourInDay)
class HourInDayAdmin(admin.ModelAdmin):
    list_display = ['id', 'lunar_day']
    search_fields = ['lunar_day']
    inlines = [
        through_inline(model, verbose_name=label)
        for model, label in zip(SAO_HOUR_MODELS, HOUR_LABELS)
    ]


@admin.register(TuDaiCatThoi)
class TuDaiDayAdmin(admin.ModelAdmin):
    list_display = ['id', 'can_ngay', 'tiet_khi']
    list_filter = ['can_ngay', 'tiet_khi']
    inlines = [through_inline(TuDaiCatThoi.sao.through)]


@admin.register(QuyNhan)
class QuyNhanAdmin(admin.ModelAdmin):
    list_display = ['id', 'can_ngay', 'tiet_khi', 'am_duong', 'quy_nhan']
    list_filter = ['can_ngay', 'tiet_khi']
