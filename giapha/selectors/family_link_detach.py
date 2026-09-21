"""Detach personal-tree links from a clan -- "tách" (spec §14.4).

Every detach first SNAPSHOTS the clan person's shared fields into the family
person (`services.family_clan_field_map.clan_to_family`), then deletes the
link: the user's own tree keeps the last values it showed, and never falls
back to stale pre-link data.

Triggers (all call into here):
  * `DELETE /v1/family/links/{id}`                  -> `detach_links([link])`
  * member removed from the clan                    -> `detach_for_member`
  * clan soft-deleted                               -> `detach_for_clan`
  * clan person soft-deleted                        -> `detach_for_clan_person`
A hard delete of a clan Person (admin only) cascades the link away without a
snapshot; the family person keeps whatever it stored before linking.
"""

from django.utils import timezone

from giapha.models import FamilyPerson, FamilyPersonLink
from giapha.services.family_clan_field_map import clan_to_family


def detach_links(links):
    """`links`: FamilyPersonLink instances with `clan_person` + `family_person`
    loaded. Returns the number detached."""
    now = timezone.now()
    for link in links:
        snapshot = clan_to_family(link.clan_person)
        FamilyPerson.objects.filter(id=link.family_person_id).update(updated_at=now, **snapshot)
    FamilyPersonLink.objects.filter(id__in=[link.id for link in links]).delete()
    return len(links)


def _links(**filters):
    return list(FamilyPersonLink.objects.filter(**filters).select_related('clan_person'))


def detach_for_member(clan_id, user_id):
    return detach_links(_links(clan_id=clan_id, family__user_id=user_id))


def detach_for_clan(clan_id):
    return detach_links(_links(clan_id=clan_id))


def detach_for_clan_person(clan_person_id):
    return detach_links(_links(clan_person_id=clan_person_id))
