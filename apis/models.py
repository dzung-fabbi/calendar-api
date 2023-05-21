from django.contrib.auth.models import AbstractUser, User
from django.db import models
from django.db.models.signals import post_save

lunar_day = (
    ("GIÁP TÝ", "GIÁP TÝ"),
    ("ẤT SỬU", "ẤT SỬU"),
    ("BÍNH DẦN", "BÍNH DẦN"),
    ("ĐINH MÃO", "ĐINH MÃO"),
    ("MẬU THÌN", "MẬU THÌN"),
    ("KỶ TỴ", "KỶ TỴ"),
    ("CANH NGỌ", "CANH NGỌ"),
    ("TÂN MÙI", "TÂN MÙI"),
    ("NHÂM THÂN", "NHÂM THÂN"),
    ("QUÝ DẬU", "QUÝ DẬU"),
    ("GIÁP TUẤT", "GIÁP TUẤT"),
    ("ẤT HỢI", "ẤT HỢI"),
    ("BÍNH TÝ", "BÍNH TÝ"),
    ("ĐINH SỬU", "ĐINH SỬU"),
    ("MẬU DẦN", "MẬU DẦN"),
    ("KỶ MÃO", "KỶ MÃO"),
    ("CANH THÌN", "CANH THÌN"),
    ("TÂN TỴ", "TÂN TỴ"),
    ("NHÂM NGỌ", "NHÂM NGỌ"),
    ("QUÝ MÙI", "QUÝ MÙI"),
    ("GIÁP THÂN", "GIÁP THÂN"),
    ("ẤT DẬU", "ẤT DẬU"),
    ("BÍNH TUẤT", "BÍNH TUẤT"),
    ("ĐINH HỢI", "ĐINH HỢI"),
    ("MẬU TÝ", "MẬU TÝ"),
    ("KỶ SỬU", "KỶ SỬU"),
    ("CANH DẦN", "CANH DẦN"),
    ("TÂN MÃO", "TÂN MÃO"),
    ("NHÂM THÌN", "NHÂM THÌN"),
    ("QUÝ TỴ", "QUÝ TỴ"),
    ("GIÁP NGỌ", "GIÁP NGỌ"),
    ("ẤT MÙI", "ẤT MÙI"),
    ("BÍNH THÂN", "BÍNH THÂN"),
    ("ĐINH DẬU", "ĐINH DẬU"),
    ("MẬU TUẤT", "MẬU TUẤT"),
    ("KỶ HỢI", "KỶ HỢI"),
    ("CANH TÝ", "CANH TÝ"),
    ("TÂN SỬU", "TÂN SỬU"),
    ("NHÂM DẦN", "NHÂM DẦN"),
    ("QUÝ MÃO", "QUÝ MÃO"),
    ("GIÁP THÌN", "GIÁP THÌN"),
    ("ẤT TỴ", "ẤT TỴ"),
    ("BÍNH NGỌ", "BÍNH NGỌ"),
    ("ĐINH MÙI", "ĐINH MÙI"),
    ("MẬU THÂN", "MẬU THÂN"),
    ("KỶ DẬU", "KỶ DẬU"),
    ("CANH TUẤT", "CANH TUẤT"),
    ("TÂN HỢI", "TÂN HỢI"),
    ("NHÂM TÝ", "NHÂM TÝ"),
    ("QUÝ SỬU", "QUÝ SỬU"),
    ("GIÁP DẦN", "GIÁP DẦN"),
    ("ẤT MÃO", "ẤT MÃO"),
    ("BÍNH THÌN", "BÍNH THÌN"),
    ("ĐINH TỴ", "ĐINH TỴ"),
    ("MẬU NGỌ", "MẬU NGỌ"),
    ("KỶ MÙI", "KỶ MÙI"),
    ("CANH THÂN", "CANH THÂN"),
    ("TÂN DẬU", "TÂN DẬU"),
    ("NHÂM TUẤT", "NHÂM TUẤT"),
    ("QUÝ HỢI", "QUÝ HỢI"),
)


class ItemBase(models.Model):
    year = models.CharField(max_length=255, choices=lunar_day, unique=True)
    is_active = models.BooleanField(default=True, editable=False)

    class Meta:
        abstract = True


good_ugly_start = (
    (0, "Không xác định"),
    (1, "Sao tốt"),
    (2, "Sao xấu")
)

is_mountain = (
    (1, "Cung"),
    (2, "Sơn")
)


class Sao(models.Model):
    name = models.CharField(max_length=255, verbose_name="Tên sao")
    property = models.TextField(null=True, verbose_name="Thuộc tính", blank=True)
    good_ugly_stars = models.IntegerField(blank=False, null=False, choices=good_ugly_start, verbose_name="Sao tốt xấu")
    is_mountain = models.IntegerField(blank=True, null=True, choices=is_mountain, verbose_name="Thuộc cung hay sơn")

    class Meta:
        db_table = "sao"
        verbose_name = "Sao"
        verbose_name_plural = "Sao"

    def __str__(self):
        return self.name


month = (
    (1, 1),
    (2, 2),
    (3, 3),
    (4, 4),
    (5, 5),
    (6, 6),
    (7, 7),
    (8, 8),
    (9, 9),
    (10, 10),
    (11, 11),
    (12, 12),
)


class TietKhi(models.Model):
    tiet_khi = models.CharField(max_length=255)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    year = models.CharField(max_length=255)
    gio_soc = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "tiet_khi"


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


can_ngay = (
    ("Giáp", "Tý"),
    ("Ất", "Sửu"),
    ("Bính", "Dần"),
    ("Đinh", "Mão"),
    ("Mậu", "Thìn"),
    ("Kỷ", "Tỵ"),
    ("Canh", "Ngọ"),
    ("Tân", "Mùi"),
    ("Nhâm", "Thân"),
    ("Quý", "Dậu"),
)

tiet_khi = (
    ("Lập Xuân", "Lập Xuân"),
    ("Vũ Thủy", "Vũ Thủy"),
    ("Kinh Trập", "Kinh Trập"),
    ("Xuân Phân", "Xuân Phân"),
    ("Thanh Minh", "Thanh Minh"),
    ("Cốc Vũ", "Cốc Vũ"),
    ("Lập Hạ", "Lập Hạ"),
    ("Tiểu Mãn", "Tiểu Mãn"),
    ("Mang Chủng", "Mang Chủng"),
    ("Hạ Chí", "Hạ Chí"),
    ("Tiểu Thử", "Tiểu Thử"),
    ("Đại Thử", "Đại Thử"),
    ("Lập Thu", "Lập Thu"),
    ("Xử Thử", "Xử Thử"),
    ("Bạch Lộ", "Bạch Lộ"),
    ("Thu Phân", "Thu Phân"),
    ("Hàn Lộ", "Hàn Lộ"),
    ("Sương Giáng", "Sương Giáng"),
    ("Lập Đông", "Lập Đông"),
    ("Tiểu Tuyết", "Tiểu Tuyết"),
    ("Đại Tuyết", "Đại Tuyết"),
    ("Đông Chí", "Đông Chí"),
    ("Tiểu Hàn", "Tiểu Hàn"),
    ("Đại Hàn", "Đại Hàn"),
)

HOURS = (
    ("Tý", "Tý"),
    ("Sửu", "Sửu"),
    ("Dần", "Dần"),
    ("Mão", "Mão"),
    ("Thìn", "Thìn"),
    ("Tỵ", "Tỵ"),
    ("Ngọ", "Ngọ"),
    ("Mùi", "Mùi"),
    ("Thân", "Thân"),
    ("Dậu", "Dậu"),
    ("Tuất", "Tuất"),
    ("Hợi", "Hợi"),
)

AM_DUONG = (
    ("Âm quý", "Âm quý"),
    ("Dương quý", "Dương quý"),
)


class QuyNhan(models.Model):
    can_ngay = models.CharField(max_length=255, choices=can_ngay, verbose_name="Can ngày")
    tiet_khi = models.CharField(max_length=255, choices=tiet_khi, verbose_name="Tiết khí")
    hour = models.CharField(max_length=255, choices=HOURS, verbose_name="Giờ")
    am_duong = models.CharField(max_length=255, null=True, verbose_name="Âm dương", choices=AM_DUONG)
    quy_nhan = models.CharField(max_length=255, null=True, verbose_name="Quý nhân", choices=HOURS)

    class Meta:
        db_table = "quy_nhan"
        verbose_name = "Quý nhân đăng thiên môn"
        verbose_name_plural = "Quý nhân đăng thiên môn"


class TuDaiCatThoi(models.Model):
    hour = models.CharField(max_length=255, choices=HOURS, verbose_name="Giờ")
    can_ngay = models.CharField(max_length=255, null=True, choices=can_ngay, verbose_name="Can ngày")
    tiet_khi = models.CharField(max_length=255, choices=tiet_khi, verbose_name="Tiết khí")
    sao = models.ManyToManyField(Sao, through='TuDaiCatThoiSao', related_name='sao')

    class Meta:
        db_table = "tu_dai_cat_thoi"
        verbose_name = "Tứ đại cát thời"
        verbose_name_plural = "Tứ đại cát thời"


class TuDaiCatThoiSao(models.Model):
    tudaicatthoi = models.ForeignKey(TuDaiCatThoi, on_delete=models.CASCADE)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Sao"
        verbose_name_plural = "Sao"


class ThanSatByYear(ItemBase):
    sao = models.ManyToManyField(Sao, through='ThanSatByYearSao')

    class Meta:
        db_table = "than_sat_by_year"
        verbose_name = "Thần sát theo năm"
        verbose_name_plural = "Thần sát theo năm"

    def __str__(self):
        return self.year


cung_son = (
    (1, "Cung"),
    (2, "Son"),
)

direction = (
    ("Khảm", "Khảm"),
    ("Cấn", "Cấn"),
    ("Chấn", "Chấn"),
    ("Tốn", "Tốn"),
    ("Ly", "Ly"),
    ("Khôn", "Khôn"),
    ("Đoài", "Đoài"),
    ("Càn", "Càn"),
    ("Nhâm", "Nhâm"),
    ("Quý", "Quý"),
    ("Tý", "Tý"),
    ("Sửu", "Sửu"),
    ("Dần", "Dần"),
    ("Giáp", "Giáp"),
    ("Mão", "Mão"),
    ("Ất", "Ất"),
    ("Thìn", "Thìn"),
    ("Tốn", "Tốn"),
    ("Tỵ", "Tỵ"),
    ("Bính", "Bính"),
    ("Ngọ", "Ngọ"),
    ("Đinh", "Đinh"),
    ("Mùi", "Mùi"),
    ("Khôn", "Khôn"),
    ("Thân", "Thân"),
    ("Canh", "Canh"),
    ("Dậu", "Dậu"),
    ("Tân", "Tân"),
    ("Tuất", "Tuất"),
    ("Hợi", "Hợi"),
    ("Mậu", "Mậu"),
    ("Trung", "Trung"),
    ("Kỷ", "Kỷ"),
)


class ThanSatByYearSao(models.Model):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    than_sat_year = models.ForeignKey(ThanSatByYear, on_delete=models.CASCADE)
    cung_son = models.IntegerField(choices=cung_son)
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


class SaoMonth1(models.Model):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    than_sat_month = models.ForeignKey(ThanSatByMonth, on_delete=models.CASCADE)
    cung_son = models.IntegerField(choices=cung_son)
    direction = models.CharField(choices=direction, max_length=255, verbose_name="Phương hướng")

    class Meta:
        verbose_name = "Sao tháng 1"
        verbose_name_plural = "Sao tháng 1"


class SaoMonth2(models.Model):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    than_sat_month = models.ForeignKey(ThanSatByMonth, on_delete=models.CASCADE)
    cung_son = models.IntegerField(choices=cung_son)
    direction = models.CharField(choices=direction, max_length=255, verbose_name="Phương hướng")

    class Meta:
        verbose_name = "Sao tháng 2"
        verbose_name_plural = "Sao tháng 2"


class SaoMonth3(models.Model):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    than_sat_month = models.ForeignKey(ThanSatByMonth, on_delete=models.CASCADE)
    cung_son = models.IntegerField(choices=cung_son)
    direction = models.CharField(choices=direction, max_length=255, verbose_name="Phương hướng")

    class Meta:
        verbose_name = "Sao tháng 3"
        verbose_name_plural = "Sao tháng 3"


class SaoMonth4(models.Model):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    than_sat_month = models.ForeignKey(ThanSatByMonth, on_delete=models.CASCADE)
    cung_son = models.IntegerField(choices=cung_son)
    direction = models.CharField(choices=direction, max_length=255, verbose_name="Phương hướng")

    class Meta:
        verbose_name = "Sao tháng 4"
        verbose_name_plural = "Sao tháng 4"


class SaoMonth5(models.Model):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    than_sat_month = models.ForeignKey(ThanSatByMonth, on_delete=models.CASCADE)
    cung_son = models.IntegerField(choices=cung_son)
    direction = models.CharField(choices=direction, max_length=255, verbose_name="Phương hướng")

    class Meta:
        verbose_name = "Sao tháng 5"
        verbose_name_plural = "Sao tháng 5"


class SaoMonth6(models.Model):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    than_sat_month = models.ForeignKey(ThanSatByMonth, on_delete=models.CASCADE)
    cung_son = models.IntegerField(choices=cung_son)
    direction = models.CharField(choices=direction, max_length=255, verbose_name="Phương hướng")

    class Meta:
        verbose_name = "Sao tháng 6"
        verbose_name_plural = "Sao tháng 6"


class SaoMonth7(models.Model):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    than_sat_month = models.ForeignKey(ThanSatByMonth, on_delete=models.CASCADE)
    cung_son = models.IntegerField(choices=cung_son)
    direction = models.CharField(choices=direction, max_length=255, verbose_name="Phương hướng")

    class Meta:
        verbose_name = "Sao tháng 7"
        verbose_name_plural = "Sao tháng 7"


class SaoMonth8(models.Model):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    than_sat_month = models.ForeignKey(ThanSatByMonth, on_delete=models.CASCADE)
    cung_son = models.IntegerField(choices=cung_son)
    direction = models.CharField(choices=direction, max_length=255, verbose_name="Phương hướng")

    class Meta:
        verbose_name = "Sao tháng 8"
        verbose_name_plural = "Sao tháng 8"


class SaoMonth9(models.Model):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    than_sat_month = models.ForeignKey(ThanSatByMonth, on_delete=models.CASCADE)
    cung_son = models.IntegerField(choices=cung_son)
    direction = models.CharField(choices=direction, max_length=255, verbose_name="Phương hướng")

    class Meta:
        verbose_name = "Sao tháng 9"
        verbose_name_plural = "Sao tháng 9"


class SaoMonth10(models.Model):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    than_sat_month = models.ForeignKey(ThanSatByMonth, on_delete=models.CASCADE)
    cung_son = models.IntegerField(choices=cung_son)
    direction = models.CharField(choices=direction, max_length=255, verbose_name="Phương hướng")

    class Meta:
        verbose_name = "Sao tháng 10"
        verbose_name_plural = "Sao tháng 10"


class SaoMonth11(models.Model):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    than_sat_month = models.ForeignKey(ThanSatByMonth, on_delete=models.CASCADE)
    cung_son = models.IntegerField(choices=cung_son)
    direction = models.CharField(choices=direction, max_length=255, verbose_name="Phương hướng")

    class Meta:
        verbose_name = "Sao tháng 11"
        verbose_name_plural = "Sao tháng 11"


class SaoMonth12(models.Model):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    than_sat_month = models.ForeignKey(ThanSatByMonth, on_delete=models.CASCADE)
    cung_son = models.IntegerField(choices=cung_son)
    direction = models.CharField(choices=direction, max_length=255, verbose_name="Phương hướng")

    class Meta:
        verbose_name = "Sao tháng 12"
        verbose_name_plural = "Sao tháng 12"


class BookCalendar(models.Model):
    work = models.CharField(max_length=255)
    date = models.DateField()
    email = models.EmailField(max_length=255, null=True, blank=True)
    status = models.IntegerField(default=0)
    phone = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Lịch đặt"
        verbose_name_plural = "Lịch đặt"


class AppointmentDate(models.Model):
    name = models.CharField(max_length=255)
    date = models.DateField(null=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        db_table = "appointment_dates"
        verbose_name = "Lịch hẹn"
        verbose_name_plural = "Lịch hẹn"


class DateConfig(models.Model):
    very_good_from = models.FloatField(verbose_name="Ngày rất tốt")
    good_from = models.FloatField(verbose_name="Ngày tốt")
    ugly_from = models.FloatField(verbose_name="Ngày xấu")

    class Meta:
        verbose_name = "Cài đặt ngày tốt xấu"
        verbose_name_plural = "Cài đặt ngày tốt xấu"


class HoursConfig(models.Model):
    very_good = models.FloatField(verbose_name="Giờ rất tốt")
    good = models.FloatField(verbose_name="Giờ tốt")

    class Meta:
        verbose_name = "Cài đặt giờ tốt xấu"
        verbose_name_plural = "Cài đặt giờ tốt xấu"


class BankConfig(models.Model):
    account_number = models.CharField(max_length=255, verbose_name="Số tài khoản")
    account_holder = models.CharField(max_length=255, verbose_name="Chủ tài khoản")
    bank = models.CharField(max_length=255, verbose_name="Ngân hàng")
    branch = models.CharField(max_length=255, verbose_name="Chi nhánh", null=True, blank=True)

    class Meta:
        verbose_name = "Ngân hàng"
        verbose_name_plural = "Ngân hàng"


STATUS_TRANSACTION = (
    (0, 'Tạo mới'),
    (1, 'Hoàn thành')
)


class BankTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6, verbose_name="code")
    status = models.IntegerField(verbose_name="Trạng thái", default=0, choices=STATUS_TRANSACTION)

    class Meta:
        verbose_name = "Giao dịch"
        verbose_name_plural = "Giao dịch"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_free = models.IntegerField(verbose_name="Thành viên trả phí", default=0)
    expiry_datetime = models.DateField(verbose_name="Thời gian hết hạn", null=True)

    def create_user_profile(sender, instance, created, **kwargs):
        if created:
            profile, created = UserProfile.objects.get_or_create(user=instance)

    post_save.connect(create_user_profile, sender=User)
    # other fields here
