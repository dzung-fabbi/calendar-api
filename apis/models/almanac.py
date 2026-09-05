"""Core almanac tables: solar terms, the per-day star sheet, and the day's hours."""

from django.db import models

from apis.models.choices import lunar_day, month
from apis.models.stars import Sao


class TietKhi(models.Model):
    tiet_khi = models.CharField(max_length=255)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    year = models.CharField(max_length=255)
    gio_soc = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tiet_khi"
        indexes = [
            # HomeAPIView orders by start_time to find the term covering a
            # date; TietkhiAPIView filters on (tiet_khi, start_time year).
            models.Index(fields=['start_time'], name='tiet_khi_start_idx'),
            models.Index(fields=['tiet_khi', 'start_time'], name='tiet_khi_name_start_idx'),
        ]


class HiepKy(models.Model):
    id = models.AutoField(primary_key=True)
    month = models.IntegerField(choices=month, verbose_name="Tháng")
    lunar_day = models.CharField(max_length=255, verbose_name="Ngày can chi", choices=lunar_day)
    good_stars = models.TextField(blank=True, null=True, verbose_name="Sao tốt", editable=False)
    ugly_stars = models.TextField(blank=True, null=True, verbose_name="Sao xấu", editable=False)
    should_things = models.TextField(blank=True, null=True, verbose_name="Việc nên làm")
    no_should_things = models.TextField(blank=True, null=True, verbose_name="Việc không nên làm")
    sao = models.ManyToManyField(Sao, through='SaoHiepKy', related_name='test')

    class Meta:
        db_table = "hiep_ky"
        verbose_name = "Sao theo ngày"
        verbose_name_plural = "Sao theo ngày"
        unique_together = ('month', 'lunar_day')


class SaoHiepKy(models.Model):
    hiepky = models.ForeignKey(HiepKy, on_delete=models.CASCADE, verbose_name="Ngày", null=True, blank=True)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Sao tốt xấu"
        verbose_name_plural = "Sao theo ngày"


class HourInDay(models.Model):
    lunar_day = models.CharField(max_length=255, verbose_name="Ngày can chi", choices=lunar_day, unique=True)
    hour_1 = models.ManyToManyField(Sao, through='SaoHour1', related_name='hour_1')
    hour_2 = models.ManyToManyField(Sao, through='SaoHour2', related_name='hour_2')
    hour_3 = models.ManyToManyField(Sao, through='SaoHour3', related_name='hour_3')
    hour_4 = models.ManyToManyField(Sao, through='SaoHour4', related_name='hour_4')
    hour_5 = models.ManyToManyField(Sao, through='SaoHour5', related_name='hour_5')
    hour_6 = models.ManyToManyField(Sao, through='SaoHour6', related_name='hour_6')
    hour_7 = models.ManyToManyField(Sao, through='SaoHour7', related_name='hour_7')
    hour_8 = models.ManyToManyField(Sao, through='SaoHour8', related_name='hour_8')
    hour_9 = models.ManyToManyField(Sao, through='SaoHour9', related_name='hour_9')
    hour_10 = models.ManyToManyField(Sao, through='SaoHour10', related_name='hour_10')
    hour_11 = models.ManyToManyField(Sao, through='SaoHour11', related_name='hour_11')
    hour_12 = models.ManyToManyField(Sao, through='SaoHour12', related_name='hour_12')

    class Meta:
        db_table = "hour_in_days"
        verbose_name = "Giờ trong ngày"
        verbose_name_plural = "Giờ trong ngày"
