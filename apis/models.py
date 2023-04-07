from django.db import models


class ItemBase(models.Model):
    year = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)

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
    property = models.TextField(null=True, verbose_name="Thuộc tính")
    good_ugly_stars = models.IntegerField(blank=False, null=False, choices=good_ugly_start, verbose_name="Sao tốt xấu")
    is_mountain = models.TextField(blank=True, null=True, choices=is_mountain, verbose_name="Thuộc cung hay sơn")

    class Meta:
        db_table = "sao"

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

class HiepKy(models.Model):
    month = models.IntegerField(choices=month, verbose_name="Tháng")
    lunar_day = models.CharField(max_length=255, verbose_name="Ngày can chi", choices=lunar_day)
    good_stars = models.TextField(blank=True, null=True, verbose_name="Sao tốt", editable=False)
    ugly_stars = models.TextField(blank=True, null=True, verbose_name="Sao xấu", editable=False)
    should_things = models.TextField(blank=True, null=True, verbose_name="Việc nên làm")
    no_should_things = models.TextField(blank=True, null=True, verbose_name="Việc không nên làm")
    sao = models.ManyToManyField(Sao, through='SaoHiepKy', related_name='test')

    def get_fk(self):
        return self.sao.name

    class Meta:
        db_table = "hiep_ky"
        verbose_name = "Sao theo ngày"
        verbose_name_plural = "Sao theo ngày"






class SaoHiepKy(models.Model):
    hiepky = models.ForeignKey(HiepKy, on_delete=models.CASCADE)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)

    def get_fk(self):
        return self.sao.name


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


class SaoHour1(models.Model):
    hour_1 = models.ForeignKey(HourInDay, on_delete=models.CASCADE)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)


class SaoHour2(models.Model):
    hour_2 = models.ForeignKey(HourInDay, on_delete=models.CASCADE)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)


class SaoHour3(models.Model):
    hour_3 = models.ForeignKey(HourInDay, on_delete=models.CASCADE)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)


class SaoHour4(models.Model):
    hour_4 = models.ForeignKey(HourInDay, on_delete=models.CASCADE)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)


class SaoHour5(models.Model):
    hour_5 = models.ForeignKey(HourInDay, on_delete=models.CASCADE)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)


class SaoHour6(models.Model):
    hour_6 = models.ForeignKey(HourInDay, on_delete=models.CASCADE)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)


class SaoHour7(models.Model):
    hour_7 = models.ForeignKey(HourInDay, on_delete=models.CASCADE)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)


class SaoHour8(models.Model):
    hour_8 = models.ForeignKey(HourInDay, on_delete=models.CASCADE)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)


class SaoHour9(models.Model):
    hour_9 = models.ForeignKey(HourInDay, on_delete=models.CASCADE)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)


class SaoHour10(models.Model):
    hour_10 = models.ForeignKey(HourInDay, on_delete=models.CASCADE)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)


class SaoHour11(models.Model):
    hour_11 = models.ForeignKey(HourInDay, on_delete=models.CASCADE)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)


class SaoHour12(models.Model):
    hour_12 = models.ForeignKey(HourInDay, on_delete=models.CASCADE)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)


class QuyNhan(models.Model):
    can_ngay = models.CharField(max_length=255)
    tiet_khi = models.CharField(max_length=255)
    hour = models.CharField(max_length=255)
    am_duong = models.CharField(max_length=255, null=True)
    quy_nhan = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = "quy_nhan"


class TuDaiCatThoiOld(models.Model):
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
        db_table = "tu_dai_cat_thoi_old"


class TuDaiCatThoi(models.Model):
    hour = models.CharField(max_length=255)
    can_ngay = models.CharField(max_length=255, null=True)
    tiet_khi = models.CharField(max_length=255)

    class Meta:
        db_table = "tu_dai_cat_thoi"


class TuDaiCatThoiSao(models.Model):
    tudaicatthoi = models.ForeignKey(TuDaiCatThoi, on_delete=models.CASCADE)
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)



class KhaiSonTuPhuongCat(ItemBase):
    star_name = models.CharField(max_length=255, blank=True, null=True)
    direction = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "khai_son_tu_phuong_cat"


class TamNguyenTuBach(ItemBase):
    nguyen = models.CharField(max_length=255, blank=True, null=True)
    bach_1 = models.CharField(max_length=255, blank=True, null=True)
    bach_6 = models.CharField(max_length=255, blank=True, null=True)
    bach_8 = models.CharField(max_length=255, blank=True, null=True)
    tu_9 = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "tam_nguyen_tu_bach"


class CaiSonHoangDao(ItemBase):
    tham_lang = models.CharField(max_length=255, blank=True, null=True)
    cu_mon = models.CharField(max_length=255, blank=True, null=True)
    vu_khuc = models.CharField(max_length=255, blank=True, null=True)
    van_khuc = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "cai_son_hoang_dao"


class ThongThienKhieu(ItemBase):
    truoc_phuong_tam_hop = models.CharField(max_length=255, blank=True, null=True)
    sau_phuong_tam_hop = models.CharField(max_length=255, blank=True, null=True)
    note = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "thong_thien_khieu"


class TauMaLucNham(ItemBase):
    than_hau = models.CharField(max_length=255, blank=True, null=True)
    cong_tao = models.CharField(max_length=255, blank=True, null=True)
    thien_cuong = models.CharField(max_length=255, blank=True, null=True)
    thang_quang = models.CharField(max_length=255, blank=True, null=True)
    truyen_tong = models.CharField(max_length=255, blank=True, null=True)
    ha_khoi = models.CharField(max_length=255, blank=True, null=True)
    note = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "tau_ma_luc_nham"


class TuLoiTamNguyen(ItemBase):
    thai_duong = models.CharField(max_length=255, blank=True, null=True)
    thai_am = models.CharField(max_length=255, blank=True, null=True)
    long_duc = models.CharField(max_length=255, blank=True, null=True)
    phuc_duc = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "tu_loi_tam_nguyen"


class KhaiSonTuPhuongHung(ItemBase):
    thai_tue = models.CharField(max_length=255, blank=True, null=True)
    tue_pha = models.CharField(max_length=255, blank=True, null=True)
    tam_sat = models.CharField(max_length=255, blank=True, null=True)
    toa_sat_huong_sat = models.CharField(max_length=255, blank=True, null=True)
    phu_thien_khong_vong = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "khai_son_tu_phuong_hung"


class KhaiSonHung(ItemBase):
    nien_khac_son_gia = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "khai_son_hung"


class AmPhuThaiTue(ItemBase):
    am_phu_thai_tue = models.CharField(max_length=255, blank=True, null=True)
    luc_hai = models.CharField(max_length=255, blank=True, null=True)
    tu_phu = models.CharField(max_length=255, blank=True, null=True)
    cuu_thoai = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "am_phu_thai_tue"


class LapHuongHung(ItemBase):
    tuan_son_la_hau = models.CharField(max_length=255, blank=True, null=True)
    benh_phu = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "lap_huong_hung"


class TuPhuongHung(ItemBase):
    thien_quan_phu = models.CharField(max_length=255, blank=True, null=True)
    dai_tuong_quan = models.CharField(max_length=255, blank=True, null=True)
    dia_quan_phu = models.CharField(max_length=255, blank=True, null=True)
    luc_si = models.CharField(max_length=255, blank=True, null=True)
    tam_that = models.CharField(max_length=255, blank=True, null=True)
    tam_menh = models.CharField(max_length=255, blank=True, null=True)
    tue_hinh = models.CharField(max_length=255, blank=True, null=True)
    hoang_phan = models.CharField(max_length=255, blank=True, null=True)
    phi_liem = models.CharField(max_length=255, blank=True, null=True)
    tang_mon = models.CharField(max_length=255, blank=True, null=True)
    tam_quan = models.CharField(max_length=255, blank=True, null=True)
    dieu_khach = models.CharField(max_length=255, blank=True, null=True)
    kim_than = models.CharField(max_length=255, blank=True, null=True)
    doc_hoa = models.CharField(max_length=255, blank=True, null=True)
    pha_bai_ngu_qui = models.CharField(max_length=255, blank=True, null=True)
    dai_sat = models.CharField(max_length=255, blank=True, null=True)
    bach_ho = models.CharField(max_length=255, blank=True, null=True)
    ngu_qui = models.CharField(max_length=255, blank=True, null=True)
    cau_vi = models.CharField(max_length=255, blank=True, null=True)
    tu_phu = models.CharField(max_length=255, blank=True, null=True)
    phi_vien = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "tu_phuong_hung"


class TuPhuongHungThang(ItemBase):
    star_name = models.CharField(max_length=255, blank=True, null=True)
    month_1 = models.CharField(max_length=255, blank=True, null=True)
    month_2 = models.CharField(max_length=255, blank=True, null=True)
    month_3 = models.CharField(max_length=255, blank=True, null=True)
    month_4 = models.CharField(max_length=255, blank=True, null=True)
    month_5 = models.CharField(max_length=255, blank=True, null=True)
    month_6 = models.CharField(max_length=255, blank=True, null=True)
    month_7 = models.CharField(max_length=255, blank=True, null=True)
    month_8 = models.CharField(max_length=255, blank=True, null=True)
    month_9 = models.CharField(max_length=255, blank=True, null=True)
    month_10 = models.CharField(max_length=255, blank=True, null=True)
    month_11 = models.CharField(max_length=255, blank=True, null=True)
    month_12 = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "tu_phuong_hung_thang"


class KhaiSonHungThang(ItemBase):
    star_name = models.CharField(max_length=255, blank=True, null=True)
    month_1 = models.CharField(max_length=255, blank=True, null=True)
    month_2 = models.CharField(max_length=255, blank=True, null=True)
    month_3 = models.CharField(max_length=255, blank=True, null=True)
    month_4 = models.CharField(max_length=255, blank=True, null=True)
    month_5 = models.CharField(max_length=255, blank=True, null=True)
    month_6 = models.CharField(max_length=255, blank=True, null=True)
    month_7 = models.CharField(max_length=255, blank=True, null=True)
    month_8 = models.CharField(max_length=255, blank=True, null=True)
    month_9 = models.CharField(max_length=255, blank=True, null=True)
    month_10 = models.CharField(max_length=255, blank=True, null=True)
    month_11 = models.CharField(max_length=255, blank=True, null=True)
    month_12 = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "khai_son_hung_thang"


class LapHuongHungThang(ItemBase):
    star_name = models.CharField(max_length=255, blank=True, null=True)
    month_1 = models.CharField(max_length=255, blank=True, null=True)
    month_2 = models.CharField(max_length=255, blank=True, null=True)
    month_3 = models.CharField(max_length=255, blank=True, null=True)
    month_4 = models.CharField(max_length=255, blank=True, null=True)
    month_5 = models.CharField(max_length=255, blank=True, null=True)
    month_6 = models.CharField(max_length=255, blank=True, null=True)
    month_7 = models.CharField(max_length=255, blank=True, null=True)
    month_8 = models.CharField(max_length=255, blank=True, null=True)
    month_9 = models.CharField(max_length=255, blank=True, null=True)
    month_10 = models.CharField(max_length=255, blank=True, null=True)
    month_11 = models.CharField(max_length=255, blank=True, null=True)
    month_12 = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "lap_huong_hung_thang"


class TamKyThang(ItemBase):
    tam_ky = models.CharField(max_length=255, blank=True, null=True)
    month_1 = models.CharField(max_length=255, blank=True, null=True)
    month_2 = models.CharField(max_length=255, blank=True, null=True)
    month_3 = models.CharField(max_length=255, blank=True, null=True)
    month_4 = models.CharField(max_length=255, blank=True, null=True)
    month_5 = models.CharField(max_length=255, blank=True, null=True)
    month_6 = models.CharField(max_length=255, blank=True, null=True)
    month_7 = models.CharField(max_length=255, blank=True, null=True)
    month_8 = models.CharField(max_length=255, blank=True, null=True)
    month_9 = models.CharField(max_length=255, blank=True, null=True)
    month_10 = models.CharField(max_length=255, blank=True, null=True)
    month_11 = models.CharField(max_length=255, blank=True, null=True)
    month_12 = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "tam_ky_thang"


class ThanSatByMonth(ItemBase):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    month_1 = models.CharField(max_length=255, blank=True, null=True)
    month_2 = models.CharField(max_length=255, blank=True, null=True)
    month_3 = models.CharField(max_length=255, blank=True, null=True)
    month_4 = models.CharField(max_length=255, blank=True, null=True)
    month_5 = models.CharField(max_length=255, blank=True, null=True)
    month_6 = models.CharField(max_length=255, blank=True, null=True)
    month_7 = models.CharField(max_length=255, blank=True, null=True)
    month_8 = models.CharField(max_length=255, blank=True, null=True)
    month_9 = models.CharField(max_length=255, blank=True, null=True)
    month_10 = models.CharField(max_length=255, blank=True, null=True)
    month_11 = models.CharField(max_length=255, blank=True, null=True)
    month_12 = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "than_sat_by_month"


class ThanSatByYear(ItemBase):
    sao = models.ForeignKey(Sao, on_delete=models.CASCADE)
    direction = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "than_sat_by_year"

