from django.db import models


class HiepKy(models.Model):
    month = models.IntegerField()
    lunar_day = models.CharField(max_length=255)
    good_stars = models.TextField(blank=True, null=True)
    ugly_stars = models.TextField(blank=True, null=True)
    should_things = models.TextField(blank=True, null=True)
    no_should_things = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "hiep_ky"


class TietKhi(models.Model):
    tiet_khi = models.CharField(max_length=255)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    year = models.CharField(max_length=255)
    gio_soc = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tiet_khi"


class HourInDay(models.Model):
    lunar_day = models.CharField(max_length=255)
    hour_1 = models.TextField(blank=True, null=True)
    hour_2 = models.TextField(blank=True, null=True)
    hour_3 = models.TextField(blank=True, null=True)
    hour_4 = models.TextField(blank=True, null=True)
    hour_5 = models.TextField(blank=True, null=True)
    hour_6 = models.TextField(blank=True, null=True)
    hour_7 = models.TextField(blank=True, null=True)
    hour_8 = models.TextField(blank=True, null=True)
    hour_9 = models.TextField(blank=True, null=True)
    hour_10 = models.TextField(blank=True, null=True)
    hour_11 = models.TextField(blank=True, null=True)
    hour_12 = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "hour_in_days"


class QuyNhan(models.Model):
    can_ngay = models.CharField(max_length=255)
    tiet_khi = models.CharField(max_length=255)
    hour = models.CharField(max_length=255)
    am_duong = models.CharField(max_length=255, null=True)
    quy_nhan = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = "quy_nhan"


class TuDaiCatThoi(models.Model):
    hour = models.CharField(max_length=255)
    can_ngay_1 = models.CharField(max_length=255, null=True)
    can_ngay_2 = models.CharField(max_length=255, null=True)
    can_ngay_3 = models.CharField(max_length=255, null=True)
    can_ngay_4 = models.CharField(max_length=255, null=True)
    can_ngay_5 = models.CharField(max_length=255, null=True)
    can_ngay_6 = models.CharField(max_length=255, null=True)
    can_ngay_7 = models.CharField(max_length=255, null=True)
    can_ngay_8 = models.CharField(max_length=255, null=True)
    can_ngay_9 = models.CharField(max_length=255, null=True)
    can_ngay_10 = models.CharField(max_length=255, null=True)
    tiet_khi = models.CharField(max_length=255)

    class Meta:
        db_table = "tu_dai_cat_thoi"
