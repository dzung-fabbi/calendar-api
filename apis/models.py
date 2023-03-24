from django.db import models


class ItemBase(models.Model):
    year = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


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


class MainNumber(models.Model):
    code = models.IntegerField()
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    number_page = models.IntegerField()

    class Meta:
        db_table = "main_number"


class BirthdayChart(models.Model):
    code = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    number_page = models.IntegerField()

    class Meta:
        db_table = "birthday_chart"


class StagesOfLife(models.Model):
    code = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    number_page = models.IntegerField()

    class Meta:
        db_table = "stages_of_life"


class LifePeak(models.Model):
    code = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    number_page = models.IntegerField()

    class Meta:
        db_table = "life_peak"


class ChallengeLife(models.Model):
    code = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    number_page = models.IntegerField()

    class Meta:
        db_table = "challenge_life"


class AttitudeNumber(models.Model):
    code = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    number_page = models.IntegerField()

    class Meta:
        db_table = "attitude_number"


class BirthdayNumber(models.Model):
    code = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    number_page = models.IntegerField()

    class Meta:
        db_table = "birthday_number"


class MissionNumber(models.Model):
    code = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    number_page = models.IntegerField()

    class Meta:
        db_table = "mission_number"


class SoulsNumber(models.Model):
    code = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    number_page = models.IntegerField()

    class Meta:
        db_table = "souls_number"


class MatureNumber(models.Model):
    code = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    number_page = models.IntegerField()

    class Meta:
        db_table = "mature_number"


class DevelopmentNumber(models.Model):
    code = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    number_page = models.IntegerField()

    class Meta:
        db_table = "development_number"


class IntrospectiveNumber(models.Model):
    code = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    number_page = models.IntegerField()

    class Meta:
        db_table = "introspective_number"


class KarmicNumber(models.Model):
    code = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    number_page = models.IntegerField()

    class Meta:
        db_table = "karmic_number"


class DeficitNumber(models.Model):
    code = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    number_page = models.IntegerField()

    class Meta:
        db_table = "deficit_number"


class PhoneNumber(models.Model):
    code = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    number_page = models.IntegerField()

    class Meta:
        db_table = "phone_number"


class PersonalMonthNumber(models.Model):
    code = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    number_page = models.IntegerField()

    class Meta:
        db_table = "personal month_number"