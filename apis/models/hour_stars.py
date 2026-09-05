"""Through-tables linking a day's twelve hours to their stars.

One model per hour of the sexagenary day (Tý .. Hợi). They differ only in the
foreign-key name and their labels; see `HourInDay` for the owning row.
"""

from django.db import models

from apis.models.almanac import HourInDay
from apis.models.stars import Sao


class SaoHour1(models.Model):
    hour_1 = models.ForeignKey(HourInDay, on_delete=models.CASCADE, verbose_name="Giờ tý")
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Giờ tý"
        verbose_name_plural = "Giờ tý"
        unique_together = ('hour_1', 'sao')


class SaoHour2(models.Model):
    hour_2 = models.ForeignKey(HourInDay, on_delete=models.CASCADE, verbose_name="Giờ sửu")
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Giờ sửu"
        verbose_name_plural = "Giờ sửu"
        unique_together = ('hour_2', 'sao')


class SaoHour3(models.Model):
    hour_3 = models.ForeignKey(HourInDay, on_delete=models.CASCADE, verbose_name="Giờ dần")
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Giờ dần"
        verbose_name_plural = "Giờ dần"
        unique_together = ('hour_3', 'sao')


class SaoHour4(models.Model):
    hour_4 = models.ForeignKey(HourInDay, on_delete=models.CASCADE, verbose_name="Giờ mão")
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Giờ mão"
        verbose_name_plural = "Giờ mão"
        unique_together = ('hour_4', 'sao')


class SaoHour5(models.Model):
    hour_5 = models.ForeignKey(HourInDay, on_delete=models.CASCADE, verbose_name="Giờ thìn")
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Giờ thìn"
        verbose_name_plural = "Giờ thìn"
        unique_together = ('hour_5', 'sao')


class SaoHour6(models.Model):
    hour_6 = models.ForeignKey(HourInDay, on_delete=models.CASCADE, verbose_name="Giờ tỵ")
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Giờ tỵ"
        verbose_name_plural = "Giờ tỵ"
        unique_together = ('hour_6', 'sao')


class SaoHour7(models.Model):
    hour_7 = models.ForeignKey(HourInDay, on_delete=models.CASCADE, verbose_name="Giờ ngọ")
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Giờ ngọ"
        verbose_name_plural = "Giờ ngọ"
        unique_together = ('hour_7', 'sao')


class SaoHour8(models.Model):
    hour_8 = models.ForeignKey(HourInDay, on_delete=models.CASCADE, verbose_name="Giờ mùi")
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Giờ mùi"
        verbose_name_plural = "Giờ mùi"
        unique_together = ('hour_8', 'sao')


class SaoHour9(models.Model):
    hour_9 = models.ForeignKey(HourInDay, on_delete=models.CASCADE, verbose_name="Giờ thân")
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Giờ thân"
        verbose_name_plural = "Giờ thân"
        unique_together = ('hour_9', 'sao',)


class SaoHour10(models.Model):
    hour_10 = models.ForeignKey(HourInDay, on_delete=models.CASCADE, verbose_name="Giờ dậu")
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Giờ dậu"
        verbose_name_plural = "Giờ dậu"
        unique_together = ('hour_10', 'sao')


class SaoHour11(models.Model):
    hour_11 = models.ForeignKey(HourInDay, on_delete=models.CASCADE, verbose_name="Giờ tuất")
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Giờ tuất"
        verbose_name_plural = "Giờ tuất"
        unique_together = ('hour_11', 'sao')


class SaoHour12(models.Model):
    hour_12 = models.ForeignKey(HourInDay, on_delete=models.CASCADE, verbose_name="Giờ hợi")
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Giờ hợi"
        verbose_name_plural = "Giờ hợi"
        unique_together = ('hour_12', 'sao')
