"""FamilyPersonLink -- "this person in my personal tree IS that person in
clan X" (plan 260919 phase 4, spec §14).

A reference, not a copy: while linked, the SHARED fields of the family person
(`services.family_clan_field_map.SHARED_FAMILY_FIELDS`) are read from the
clan person on every `GET /v1/family`; nothing is synced in the background.
Detaching (`selectors.family_link_detach`) snapshots the clan values into the
family person first, so leaving a clan never loses data.

Constraints: one link per (family person, clan) and one family person per
clan person within a family -- a user cannot claim two of their nodes are the
same clan ancestor.
"""

from django.contrib.auth.models import User
from django.db import models

from giapha.models.clan import Clan
from giapha.models.family import Family, FamilyPerson
from giapha.models.person import Person


class FamilyPersonLink(models.Model):
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='clan_links', verbose_name='Gia phả')
    family_person = models.ForeignKey(
        FamilyPerson, on_delete=models.CASCADE, related_name='clan_links', verbose_name='Người (cá nhân)',
    )
    clan = models.ForeignKey(Clan, on_delete=models.CASCADE, related_name='family_links', verbose_name='Dòng họ')
    clan_person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name='family_links', verbose_name='Người (dòng họ)',
    )
    linked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+', verbose_name='Người liên kết',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')

    class Meta:
        verbose_name = 'Liên kết cá nhân - dòng họ'
        verbose_name_plural = 'Liên kết cá nhân - dòng họ'
        unique_together = (('family_person', 'clan'), ('family', 'clan_person'))

    def __str__(self):
        return '{} -> {}'.format(self.family_person_id, self.clan_person_id)
