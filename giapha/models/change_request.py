"""ChangeRequest (đề xuất thay đổi) -- a member's proposed edit to the clan
tree outside their family scope, applied only when a reviewer approves it.

`payload_json` is validated with the real write serializer at creation (so
junk never queues) and again at approval (the tree may have moved). Applying
goes through `selectors.person_write` / `selectors.marriage_write` -- the same
path as a direct edit -- with the reviewer as revision actor.
"""

from django.contrib.auth.models import User
from django.db import models

from giapha.models.clan import Clan
from giapha.models.marriage import Marriage
from giapha.models.person import Person

CHANGE_REQUEST_ACTION = (
    ('create_person', 'Thêm người'),
    ('update_person', 'Sửa người'),
    ('delete_person', 'Xoá người'),
    ('create_marriage', 'Thêm hôn nhân'),
    ('update_marriage', 'Sửa hôn nhân'),
    ('delete_marriage', 'Xoá hôn nhân'),
)

CHANGE_REQUEST_STATUS = (
    ('pending', 'Chờ duyệt'),
    ('approved', 'Đã duyệt'),
    ('rejected', 'Bị từ chối'),
    ('expired', 'Hết hạn'),
    ('withdrawn', 'Đã rút'),
    ('stale', 'Lỗi thời'),
)


class ChangeRequest(models.Model):
    clan = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='change_requests', verbose_name='Dòng họ')
    proposer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='proposed_change_requests', verbose_name='Người đề xuất',
    )
    action = models.CharField(max_length=20, choices=CHANGE_REQUEST_ACTION, verbose_name='Hành động')
    target_person = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='change_requests', verbose_name='Người bị sửa',
    )
    target_marriage = models.ForeignKey(
        Marriage, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='change_requests', verbose_name='Hôn nhân bị sửa',
    )
    # TextField, not JSONField: MySQL 5.7 + Django 3.1 (same as PersonRevision).
    payload_json = models.TextField(default='{}', verbose_name='Nội dung đề xuất (JSON)')
    proposer_note = models.CharField(max_length=500, blank=True, verbose_name='Nguồn / lý do')
    # Staleness guard: the target's `updated_at` when the proposal was made.
    base_updated_at = models.DateTimeField(null=True, blank=True, verbose_name='Mốc dữ liệu gốc')
    # Phase 5: the target's `Person.version` at proposal time. Preferred over
    # `base_updated_at` when set; the timestamp stays for proposals created
    # before versions existed.
    base_version = models.IntegerField(null=True, blank=True, verbose_name='Phiên bản gốc')
    status = models.CharField(
        max_length=12, choices=CHANGE_REQUEST_STATUS, default='pending', verbose_name='Trạng thái',
    )
    reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_change_requests', verbose_name='Người duyệt',
    )
    review_note = models.CharField(max_length=500, blank=True, verbose_name='Ghi chú duyệt')
    # "Đóng góp" from a personal tree (phase 4): on approval of a
    # `create_person`, the new clan person is linked to this family person.
    family_person = models.ForeignKey(
        'giapha.FamilyPerson', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Người (cá nhân) đóng góp',
    )
    # Day-7 reminder sent (`expire_change_requests`); makes the job idempotent.
    reminded_at = models.DateTimeField(null=True, blank=True, verbose_name='Đã nhắc lúc')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='Ngày duyệt')

    class Meta:
        verbose_name = 'Đề xuất thay đổi'
        verbose_name_plural = 'Đề xuất thay đổi'
        indexes = [models.Index(fields=['clan', 'status'], name='giapha_cr_clan_status_idx')]

    def __str__(self):
        return '#{} {} ({})'.format(self.id, self.action, self.status)
