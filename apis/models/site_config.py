"""Admin-editable thresholds that drive the good/bad ratings."""

from django.db import models


class DateConfig(models.Model):
    very_good_from = models.FloatField(verbose_name="Ngày rất tốt")
    good_from = models.FloatField(verbose_name="Ngày tốt")
    ugly_from = models.FloatField(verbose_name="Ngày xấu")
    factor_1 = models.FloatField(verbose_name="Hệ số 1", default=1)
    factor_2 = models.FloatField(verbose_name="Hệ số 2", default=2)

    class Meta:
        verbose_name = "Cài đặt ngày tốt xấu"
        verbose_name_plural = "Cài đặt ngày tốt xấu"


class HoursConfig(models.Model):
    very_good = models.FloatField(verbose_name="Giờ rất tốt")
    good = models.FloatField(verbose_name="Giờ tốt")
    ugly = models.FloatField(verbose_name="Giờ xấu", default=2)

    class Meta:
        verbose_name = "Cài đặt giờ tốt xấu"
        verbose_name_plural = "Cài đặt giờ tốt xấu"


class DirectionConfig(models.Model):
    value = models.FloatField(verbose_name="giá trị")

    class Meta:
        verbose_name = "Cài đặt phương hướng tốt xấu"
        verbose_name_plural = "Cài đặt phương hướng tốt xấu"
