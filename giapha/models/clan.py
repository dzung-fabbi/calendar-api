"""Clan (dòng họ), its members and invite codes."""

from django.contrib.auth.models import User
from django.db import models

from giapha.models.choices import CLAN_ROLE, INVITE_ROLE, VISIBILITY


class Clan(models.Model):
    ten_ho = models.CharField(max_length=255, verbose_name='Tên họ')
    thuy_to = models.CharField(max_length=255, blank=True, verbose_name='Thuỷ tổ')
    mo_ta = models.TextField(blank=True, verbose_name='Mô tả')
    visibility = models.CharField(
        max_length=16, choices=VISIBILITY, default='private', verbose_name='Chế độ hiển thị',
    )
    # Generated when the public gia phả page ships (phase 9); NULL until then.
    public_slug = models.CharField(
        max_length=32, unique=True, null=True, blank=True, verbose_name='Slug công khai',
    )
    hide_living_details = models.BooleanField(default=True, verbose_name='Ẩn thông tin người còn sống')
    is_deleted = models.BooleanField(default=False, verbose_name='Đã xoá (mềm)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Ngày cập nhật')

    class Meta:
        verbose_name = 'Dòng họ'
        verbose_name_plural = 'Dòng họ'

    def __str__(self):
        return self.ten_ho


class ClanMember(models.Model):
    clan = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='members', verbose_name='Dòng họ')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Người dùng')
    role = models.CharField(max_length=16, choices=CLAN_ROLE, verbose_name='Vai trò')
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tham gia')

    class Meta:
        verbose_name = 'Thành viên dòng họ'
        verbose_name_plural = 'Thành viên dòng họ'
        unique_together = ('clan', 'user')

    def __str__(self):
        return '{} - {}'.format(self.clan, self.user)


class ClanInvite(models.Model):
    clan = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='invites', verbose_name='Dòng họ')
    code = models.CharField(max_length=12, unique=True, db_index=True, verbose_name='Mã mời')
    # INVITE_ROLE, not CLAN_ROLE: an invite must never be able to grant
    # ownership. Redemption re-checks this too -- admin writes bypass the
    # serializer, so the model choices alone are not a guarantee.
    role = models.CharField(max_length=16, choices=INVITE_ROLE, default='viewer', verbose_name='Vai trò')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Hết hạn lúc')
    # 0 = không giới hạn số lần dùng.
    max_uses = models.IntegerField(default=0, verbose_name='Số lần dùng tối đa')
    used_count = models.IntegerField(default=0, verbose_name='Số lần đã dùng')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Người tạo',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')

    class Meta:
        verbose_name = 'Mã mời dòng họ'
        verbose_name_plural = 'Mã mời dòng họ'

    def __str__(self):
        return self.code
