"""`GioFollow` -- per-user override of who gets a giỗ reminder.

This is an OVERRIDE table, not a subscription list. The default set of
followed people is *implicit*: the direct-line ancestors of the Person the
user is bound to (`ClanMember.person`), resolved at send time from
`selectors.person.clan_edges_all`. Only the deviations are stored:

    no row              -> default (ancestor => follow, otherwise => don't)
    row enabled=True    -> follow someone outside the direct line
    row enabled=False   -> drop an ancestor the user does not want reminders for

Materialising the default instead would need a re-sync on every tree edit
(father/mother change, new person, soft delete, member join, binding change)
for the benefit of a job that runs once a day, and would fail silently when
the sync is missed. Implicit resolution costs one extra query and self-heals.

`enabled` deliberately has NO default: every stored row is an explicit
statement, so a row written without saying which way it goes is a bug, not a
"follow".
"""

from django.contrib.auth.models import User
from django.db import models

from giapha.models.person import Person


class GioFollow(models.Model):
    # CASCADE on both sides: following a hard-deleted person is meaningless,
    # and deleting an account must leave nothing behind. A *soft*-deleted
    # Person keeps its rows -- the reminder query filters `is_deleted=False`
    # itself, so the override survives a restore intact.
    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name='gio_follows',
        verbose_name='Người được theo dõi',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='gio_follows',
        verbose_name='Người theo dõi',
    )
    enabled = models.BooleanField(verbose_name='Bật theo dõi')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Ngày tạo')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Ngày cập nhật')

    class Meta:
        verbose_name = 'Theo dõi giỗ'
        verbose_name_plural = 'Theo dõi giỗ'
        # Doubles as the lookup index (leading column `person`); the `user`
        # FK carries its own index. No further index at this scale.
        unique_together = ('person', 'user')

    def __str__(self):
        return '{} - {} ({})'.format(self.person_id, self.user_id, self.enabled)
