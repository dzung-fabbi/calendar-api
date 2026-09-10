"""Gia phả cá nhân -- one user, one family tree (`/v1/family`).

A SEPARATE model set from `Clan`/`Person`/`Marriage`, on purpose. The mobile
app's contract (`docs/gia-pha-api-spec.md`) conflicts with the clan module in
ways a shared table could not reconcile: hard delete that detaches instead of
soft delete that is blocked while children exist; `deceased` as an explicit
flag rather than derived from a death date; spouses between two people of
possibly `unknown` gender rather than a gendered husband/wife row; UUID ids the
client remaps to. The clan API keeps its semantics; this one keeps the app's.

Storage rule (spec §2.1): only the UPWARD edges (`father`/`mother`) and the
spouse pairs are persisted. `children`, `siblings`, co-parents, components and
generations are derived on every read -- a family is < 500 people, so building
an index per request is free and there is nothing to keep consistent.
"""

import uuid

from django.contrib.auth.models import User
from django.db import models

from giapha.models.choices import FAMILY_GENDER, FAMILY_PARENT_REL, FAMILY_SPOUSE_REL


class Family(models.Model):
    """The one tree a user owns. Created lazily on first access."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='family', verbose_name='Người dùng',
    )
    # "Tôi" là scalar (spec §2.2): exactly one person or none, never a flag
    # on the person row. SET_NULL so deleting that person clears it (spec §2.6).
    self_person = models.ForeignKey(
        'giapha.FamilyPerson', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Người là "tôi"',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Ngày cập nhật')

    class Meta:
        verbose_name = 'Gia phả cá nhân'
        verbose_name_plural = 'Gia phả cá nhân'

    def __str__(self):
        return 'Gia phả của {}'.format(self.user)


class FamilyPerson(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    family = models.ForeignKey(
        Family, on_delete=models.CASCADE, related_name='persons', verbose_name='Gia phả',
    )

    name = models.CharField(max_length=60, verbose_name='Họ tên')
    gender = models.CharField(
        max_length=8, choices=FAMILY_GENDER, default='unknown', verbose_name='Giới tính',
    )
    # Explicit, never inferred from a death date (spec §2.3).
    deceased = models.BooleanField(default=False, verbose_name='Đã mất')

    # Upward edges. SET_NULL = "xoá không lan" (spec §2.6): deleting a parent
    # leaves the child in place with an empty slot.
    father = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children_as_father', verbose_name='Cha',
    )
    mother = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children_as_mother', verbose_name='Mẹ',
    )
    # NULL means 'blood' (spec: "chỉ ghi khi 'adopted'").
    father_rel = models.CharField(
        max_length=8, choices=FAMILY_PARENT_REL, null=True, blank=True, verbose_name='Quan hệ với cha',
    )
    mother_rel = models.CharField(
        max_length=8, choices=FAMILY_PARENT_REL, null=True, blank=True, verbose_name='Quan hệ với mẹ',
    )

    solar_birth_date = models.DateField(null=True, blank=True, verbose_name='Ngày sinh dương')
    birth_time = models.CharField(max_length=5, null=True, blank=True, verbose_name='Giờ sinh (HH:mm)')
    birth_order = models.IntegerField(null=True, blank=True, verbose_name='Thứ tự sinh (1 = con cả)')

    # Death is recorded in the LUNAR calendar (spec §2.4); the solar date is
    # derived at write time when day+month+year are all known.
    solar_death_date = models.DateField(null=True, blank=True, verbose_name='Ngày mất dương (suy ra)')
    death_time = models.CharField(max_length=5, null=True, blank=True, verbose_name='Giờ mất (HH:mm)')
    lunar_death_day = models.IntegerField(null=True, blank=True, verbose_name='Ngày mất âm')
    lunar_death_month = models.IntegerField(null=True, blank=True, verbose_name='Tháng mất âm')
    lunar_death_year = models.IntegerField(null=True, blank=True, verbose_name='Năm mất âm')
    lunar_leap = models.BooleanField(null=True, blank=True, verbose_name='Tháng nhuận')

    # Free-text label relative to "tôi" -- a note, not a graph edge (spec §3.1).
    relationship = models.CharField(max_length=24, null=True, blank=True, verbose_name='Quan hệ với tôi')
    note = models.CharField(max_length=200, null=True, blank=True, verbose_name='Ghi chú')
    # Id of the client-side giỗ reminder event. Opaque to the server.
    gio_event_id = models.CharField(max_length=64, null=True, blank=True, verbose_name='Id sự kiện giỗ')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Ngày cập nhật')

    class Meta:
        verbose_name = 'Người trong gia phả cá nhân'
        verbose_name_plural = 'Người trong gia phả cá nhân'

    def __str__(self):
        return self.name


class FamilySpouse(models.Model):
    """One undirected spouse edge. Stored ONCE per pair, `person_a < person_b`
    by string id (`services.family_graph.canonical_pair`), so "ghi/gỡ cả hai
    bên trong một transaction" (spec §2.5) is a single row by construction.
    """

    family = models.ForeignKey(
        Family, on_delete=models.CASCADE, related_name='spouse_links', verbose_name='Gia phả',
    )
    person_a = models.ForeignKey(
        FamilyPerson, on_delete=models.CASCADE, related_name='spouse_links_a', verbose_name='Người A',
    )
    person_b = models.ForeignKey(
        FamilyPerson, on_delete=models.CASCADE, related_name='spouse_links_b', verbose_name='Người B',
    )
    type = models.CharField(
        max_length=8, choices=FAMILY_SPOUSE_REL, default='married', verbose_name='Loại',
    )

    class Meta:
        verbose_name = 'Vợ/chồng (gia phả cá nhân)'
        verbose_name_plural = 'Vợ/chồng (gia phả cá nhân)'
        unique_together = ('person_a', 'person_b')

    def __str__(self):
        return '{} - {}'.format(self.person_a_id, self.person_b_id)
