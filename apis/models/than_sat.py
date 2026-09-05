"""Thần sát: the yearly and monthly star/direction tables."""

from django.db import models

from apis.models.choices import cung_son, direction, lunar_day
from apis.models.stars import Sao


class ItemBase(models.Model):
    """Shared identity for the yearly/monthly thần sát tables.

    `ThanSatByMonth` deliberately overrides `year` with a foreign key to
    `ThanSatByYear`; only `ThanSatByYear` keeps the can-chi char field.
    """

    year = models.CharField(max_length=255, choices=lunar_day, unique=True)
    is_active = models.BooleanField(default=True, editable=False)

    class Meta:
        abstract = True


class ThanSatByYear(ItemBase):
    sao = models.ManyToManyField(Sao, through='ThanSatByYearSao')

    class Meta:
        db_table = "than_sat_by_year"
        verbose_name = "Thần sát theo năm"
        verbose_name_plural = "Thần sát theo năm"

    def __str__(self):
        return self.year


class ThanSatByYearSao(models.Model):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    than_sat_year = models.ForeignKey(ThanSatByYear, on_delete=models.CASCADE)
    cung_son = models.IntegerField(choices=cung_son, editable=False, null=True, blank=True)
    direction = models.CharField(choices=direction, max_length=255, verbose_name="Phương hướng")

    class Meta:
        db_table = "than_sat_by_year_sao"
        verbose_name = "Sao"
        verbose_name_plural = "Sao"


class ThanSatByMonth(ItemBase):
    year = models.ForeignKey(ThanSatByYear, on_delete=models.CASCADE)
    month_1 = models.ManyToManyField(Sao, through='SaoMonth1', related_name="sao_month_1")
    month_2 = models.ManyToManyField(Sao, through='SaoMonth2', related_name="sao_month_2")
    month_3 = models.ManyToManyField(Sao, through='SaoMonth3', related_name="sao_month_3")
    month_4 = models.ManyToManyField(Sao, through='SaoMonth4', related_name="sao_month_4")
    month_5 = models.ManyToManyField(Sao, through='SaoMonth5', related_name="sao_month_5")
    month_6 = models.ManyToManyField(Sao, through='SaoMonth6', related_name="sao_month_6")
    month_7 = models.ManyToManyField(Sao, through='SaoMonth7', related_name="sao_month_7")
    month_8 = models.ManyToManyField(Sao, through='SaoMonth8', related_name="sao_month_8")
    month_9 = models.ManyToManyField(Sao, through='SaoMonth9', related_name="sao_month_9")
    month_10 = models.ManyToManyField(Sao, through='SaoMonth10', related_name="sao_month_10")
    month_11 = models.ManyToManyField(Sao, through='SaoMonth11', related_name="sao_month_11")
    month_12 = models.ManyToManyField(Sao, through='SaoMonth12', related_name="sao_month_12")

    class Meta:
        db_table = "than_sat_by_month"
        verbose_name = "Thần sát theo tháng"
        verbose_name_plural = "Thần sát theo tháng"
