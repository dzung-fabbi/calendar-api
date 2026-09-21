"""Optimistic lock for clan persons (plan 260919 phase 5).

`Person.version` goes up by exactly one on EVERY write path -- update,
soft-delete, restore, change-request approval, photo confirm/delete -- so a
client that read version N can say "only if nobody changed it since".

`lock_and_bump` takes a row lock (`SELECT ... FOR UPDATE`) on the version,
compares, and sets `person.version = current + 1` on the instance; the
caller's own `save()` then writes it. Holding the lock until commit is what
makes two concurrent PATCHes with the same version produce one 200 and one
409 instead of a lost update. Must run inside `transaction.atomic()`.
"""

from giapha.models import Person


class VersionConflict(Exception):
    def __init__(self, current_version):
        self.current_version = current_version
        super().__init__('version conflict (current={})'.format(current_version))


def lock_and_bump(person, expected=None):
    current = (
        Person.objects.select_for_update().filter(id=person.id).values_list('version', flat=True).first()
    )
    if expected is not None and current != expected:
        raise VersionConflict(current)
    person.version = current + 1
    return person.version
