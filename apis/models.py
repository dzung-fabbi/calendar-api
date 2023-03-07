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
