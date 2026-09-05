"""Auspicious-hour lookups keyed by the day's heavenly stem and the solar term."""

from django.db import models

from apis.models.choices import AM_DUONG, HOURS, can_ngay, tiet_khi
from apis.models.stars import Sao


class QuyNhan(models.Model):
    can_ngay = models.CharField(max_length=255, choices=can_ngay, verbose_name="Can ngày")
    tiet_khi = models.CharField(max_length=255, choices=tiet_khi, verbose_name="Tiết khí")
    hour = models.CharField(max_length=255, choices=HOURS, verbose_name="Giờ")
    am_duong = models.CharField(max_length=255, null=True, verbose_name="Âm dương", choices=AM_DUONG)
    quy_nhan = models.CharField(max_length=255, null=True, verbose_name="Quý nhân", choices=HOURS)

    class Meta:
        db_table = "quy_nhan"
        # HomeAPIView filters on the day's stem plus the solar term.
        indexes = [models.Index(fields=['can_ngay'], name='quy_nhan_can_ngay_idx')]
        verbose_name = "Quý nhân đăng thiên môn"
        verbose_name_plural = "Quý nhân đăng thiên môn"


class TuDaiCatThoi(models.Model):
    hour = models.CharField(max_length=255, choices=HOURS, verbose_name="Giờ")
    can_ngay = models.CharField(max_length=255, null=True, choices=can_ngay, verbose_name="Can ngày")
    tiet_khi = models.CharField(max_length=255, choices=tiet_khi, verbose_name="Tiết khí")
    sao = models.ManyToManyField(Sao, through='TuDaiCatThoiSao', related_name='sao')

    class Meta:
        db_table = "tu_dai_cat_thoi"
        indexes = [models.Index(fields=['can_ngay'], name='tu_dai_can_ngay_idx')]
        verbose_name = "Tứ đại cát thời"
        verbose_name_plural = "Tứ đại cát thời"


class TuDaiCatThoiSao(models.Model):
    tudaicatthoi = models.ForeignKey(TuDaiCatThoi, on_delete=models.CASCADE)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Sao"
        verbose_name_plural = "Sao"
