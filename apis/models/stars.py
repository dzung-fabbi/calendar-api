"""The star catalogue: every other table in the app points at `Sao`."""

from django.db import models

from apis.models.choices import CALENDAR, good_ugly_start, is_mountain


class CategoryStars(models.Model):
    name = models.CharField(max_length=255, verbose_name="Tên hệ sao")

    class Meta:
        verbose_name = "Hệ sao"
        verbose_name_plural = "Hệ sao"

    def __str__(self):
        return self.name


class Sao(models.Model):
    name = models.CharField(max_length=255, verbose_name="Tên sao")
    property = models.TextField(null=True, verbose_name="Thuộc tính", blank=True)
    good_ugly_stars = models.IntegerField(blank=False, null=False, choices=good_ugly_start, verbose_name="Sao tốt xấu")
    is_mountain = models.IntegerField(blank=True, null=True, choices=is_mountain, verbose_name="Thuộc cung hay sơn")
    category = models.ForeignKey(CategoryStars, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Hệ sao")
    calendar = models.IntegerField(choices=CALENDAR, null=True, blank=True, verbose_name="Chạy theo")
    level = models.FloatField(null=True, blank=True, verbose_name="Cấp độ")
    level_year = models.FloatField(null=True, blank=True, verbose_name="Cấp độ theo năm")
    level_month = models.FloatField(null=True, blank=True, verbose_name="Cấp độ theo tháng")
    level_day = models.FloatField(null=True, blank=True, verbose_name="Cấp độ theo ngày")
    level_hours = models.FloatField(null=True, blank=True, verbose_name="Cấp độ theo giờ")
    point = models.FloatField(null=True, blank=True, verbose_name="Điểm")

    class Meta:
        db_table = "sao"
        verbose_name = "Sao"
        verbose_name_plural = "Sao"

    def __str__(self):
        return self.name
