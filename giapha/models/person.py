"""Person (thành viên gia phả) -- the central entity of the module."""

from django.db import models

from giapha.models.choices import GIOI_TINH, PARENT_KIND
from giapha.models.clan import Clan


class Person(models.Model):
    clan = models.ForeignKey(
        Clan, on_delete=models.CASCADE, related_name='persons', db_index=True, verbose_name='Dòng họ',
    )

    # Danh xưng -- gia phả VN cần đủ bộ, không cắt bớt.
    ho_ten = models.CharField(max_length=255, db_index=True, verbose_name='Họ tên')
    ten_huy = models.CharField(max_length=255, blank=True, verbose_name='Tên huý')
    ten_tu = models.CharField(max_length=255, blank=True, verbose_name='Tên tự')
    ten_hieu = models.CharField(max_length=255, blank=True, verbose_name='Tên hiệu')
    thuy_hieu = models.CharField(max_length=255, blank=True, verbose_name='Thuỵ hiệu')

    gioi_tinh = models.CharField(max_length=8, choices=GIOI_TINH, verbose_name='Giới tính')

    # Quan hệ dọc.
    father = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children_as_father', verbose_name='Cha',
    )
    mother = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children_as_mother', verbose_name='Mẹ',
    )
    parent_kind = models.CharField(
        max_length=8, choices=PARENT_KIND, default='ruot', verbose_name='Quan hệ với cha mẹ',
    )

    # Vị trí trong họ.
    generation = models.IntegerField(null=True, blank=True, db_index=True, verbose_name='Đời thứ')
    branch = models.CharField(max_length=255, blank=True, db_index=True, verbose_name='Chi/nhánh')
    birth_order = models.IntegerField(null=True, blank=True, verbose_name='Con thứ')
    is_truong = models.BooleanField(default=False, verbose_name='Con trưởng')

    # Sinh.
    birth_solar = models.DateField(null=True, blank=True, verbose_name='Ngày sinh dương lịch')
    birth_lunar_day = models.IntegerField(null=True, blank=True, verbose_name='Ngày sinh âm lịch')
    birth_lunar_month = models.IntegerField(null=True, blank=True, verbose_name='Tháng sinh âm lịch')
    birth_lunar_leap = models.BooleanField(default=False, verbose_name='Tháng nhuận (sinh)')

    # Mất -- giỗ tính theo âm lịch, ngày dương chỉ là tham chiếu.
    death_solar = models.DateField(null=True, blank=True, verbose_name='Ngày mất dương lịch')
    death_lunar_day = models.IntegerField(null=True, blank=True, verbose_name='Ngày mất âm lịch')
    death_lunar_month = models.IntegerField(null=True, blank=True, verbose_name='Tháng mất âm lịch')
    death_lunar_leap = models.BooleanField(default=False, verbose_name='Tháng nhuận (mất)')

    # Hồ sơ.
    que_quan = models.CharField(max_length=255, blank=True, verbose_name='Quê quán')
    nghe_nghiep = models.CharField(max_length=255, blank=True, verbose_name='Nghề nghiệp')
    tieu_su = models.TextField(blank=True, verbose_name='Tiểu sử')
    # Key S3/R2 cho ảnh chân dung, xử lý upload ở phase 8.
    photo_key = models.CharField(max_length=255, blank=True, verbose_name='Khoá ảnh')

    # Mộ phần.
    mo_phan_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='Vĩ độ mộ phần',
    )
    mo_phan_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True, verbose_name='Kinh độ mộ phần',
    )
    mo_phan_note = models.CharField(max_length=255, blank=True, verbose_name='Ghi chú mộ phần')

    is_deleted = models.BooleanField(default=False, verbose_name='Đã xoá (mềm)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Ngày cập nhật')

    class Meta:
        verbose_name = 'Thành viên gia phả'
        verbose_name_plural = 'Thành viên gia phả'
        indexes = [
            models.Index(fields=['clan', 'generation'], name='giapha_person_clan_gen_idx'),
            models.Index(fields=['clan', 'branch'], name='giapha_person_clan_branch_idx'),
            # Phục vụ truy vấn lịch giỗ theo âm lịch ở phase 5.
            models.Index(
                fields=['clan', 'death_lunar_month', 'death_lunar_day'],
                name='giapha_person_clan_gio_idx',
            ),
        ]

    def __str__(self):
        return self.ho_ten
