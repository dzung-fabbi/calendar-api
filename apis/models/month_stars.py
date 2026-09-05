"""Through-tables linking a monthly thần sát row to its stars and directions.

The twelve models are field-for-field identical, so the columns live on one
abstract base and each concrete model only carries its own label. Django names
each table from the concrete class (`apis_saomonth1` ...), so this is purely a
source-level change -- `makemigrations` must report no changes.
"""

from django.db import models

from apis.models.choices import cung_son, direction
from apis.models.stars import Sao
from apis.models.than_sat import ThanSatByMonth


class SaoMonthBase(models.Model):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    than_sat_month = models.ForeignKey(ThanSatByMonth, on_delete=models.CASCADE)
    cung_son = models.IntegerField(choices=cung_son, editable=False, null=True, blank=True)
    direction = models.CharField(choices=direction, max_length=255, verbose_name="Phương hướng")

    class Meta:
        abstract = True


class SaoMonth1(SaoMonthBase):
    class Meta:
        verbose_name = "Sao tháng 1"
        verbose_name_plural = "Sao tháng 1"


class SaoMonth2(SaoMonthBase):
    class Meta:
        verbose_name = "Sao tháng 2"
        verbose_name_plural = "Sao tháng 2"


class SaoMonth3(SaoMonthBase):
    class Meta:
        verbose_name = "Sao tháng 3"
        verbose_name_plural = "Sao tháng 3"


class SaoMonth4(SaoMonthBase):
    class Meta:
        verbose_name = "Sao tháng 4"
        verbose_name_plural = "Sao tháng 4"


class SaoMonth5(SaoMonthBase):
    class Meta:
        verbose_name = "Sao tháng 5"
        verbose_name_plural = "Sao tháng 5"


class SaoMonth6(SaoMonthBase):
    class Meta:
        verbose_name = "Sao tháng 6"
        verbose_name_plural = "Sao tháng 6"


class SaoMonth7(SaoMonthBase):
    class Meta:
        verbose_name = "Sao tháng 7"
        verbose_name_plural = "Sao tháng 7"


class SaoMonth8(SaoMonthBase):
    class Meta:
        verbose_name = "Sao tháng 8"
        verbose_name_plural = "Sao tháng 8"


class SaoMonth9(SaoMonthBase):
    class Meta:
        verbose_name = "Sao tháng 9"
        verbose_name_plural = "Sao tháng 9"


class SaoMonth10(SaoMonthBase):
    class Meta:
        verbose_name = "Sao tháng 10"
        verbose_name_plural = "Sao tháng 10"


class SaoMonth11(SaoMonthBase):
    class Meta:
        verbose_name = "Sao tháng 11"
        verbose_name_plural = "Sao tháng 11"


class SaoMonth12(SaoMonthBase):
    class Meta:
        verbose_name = "Sao tháng 12"
        verbose_name_plural = "Sao tháng 12"
