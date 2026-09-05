"""Audit trail for changes to a Person record."""

from django.contrib.auth.models import User
from django.db import models

from giapha.models.choices import REVISION_ACTION
from giapha.models.person import Person


class PersonRevision(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='revisions', verbose_name='Thành viên')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Người thao tác')
    action = models.CharField(max_length=8, choices=REVISION_ACTION, verbose_name='Hành động')
    # Snapshot JSON trước khi đổi. TextField vì MySQL 5.7 + Django 3.1 hỗ trợ
    # JSONField kém tin cậy.
    payload_json = models.TextField(verbose_name='Dữ liệu snapshot (JSON)')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Ngày tạo')

    class Meta:
        verbose_name = 'Lịch sử thay đổi'
        verbose_name_plural = 'Lịch sử thay đổi'

    def __str__(self):
        return '{} #{}'.format(self.person, self.action)
