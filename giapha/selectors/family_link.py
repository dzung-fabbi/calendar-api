"""Reads for personal-tree <-> clan links (plan 260919 phase 4).

`active_link_rows` is the ONE extra query `/v1/family` pays for the overlay:
links joined with their clan person's shared columns. It also filters out
links that should no longer apply (clan soft-deleted, clan person
soft-deleted, user no longer a member) -- the detach hooks remove those rows,
this filter is the belt to those braces.
"""

from giapha.models import FamilyPersonLink, Marriage, Person
from giapha.services.family_clan_field_map import CLAN_SOURCE_FIELDS

_CLAN_PERSON_COLUMNS = tuple('clan_person__' + field for field in CLAN_SOURCE_FIELDS)


def _active(queryset, user_id):
    return queryset.filter(
        clan__is_deleted=False, clan_person__is_deleted=False, clan__members__user_id=user_id,
    )


def active_link_rows(family):
    """`[{id, family_person_id, clan_id, clan_person_id, clan__ten_ho, clan_person__<shared>...}]`."""
    return list(
        _active(FamilyPersonLink.objects.filter(family_id=family.id), family.user_id)
        .order_by('id')
        .values('id', 'family_person_id', 'clan_id', 'clan_person_id', 'clan__ten_ho', *_CLAN_PERSON_COLUMNS)
    )


def links_in_clan(family, clan_id):
    """`{family_person_id: clan_person_id}` for this family's links into one clan."""
    rows = FamilyPersonLink.objects.filter(family_id=family.id, clan_id=clan_id).values_list(
        'family_person_id', 'clan_person_id',
    )
    return dict(rows)


def get_link(family, link_id):
    return FamilyPersonLink.objects.filter(family_id=family.id, id=link_id).select_related('clan_person').first()


def clan_person_rows(clan_id):
    """Live clan persons for matching/diff/import: ids, parents, shared fields."""
    return list(
        Person.objects.filter(clan_id=clan_id, is_deleted=False)
        .values('id', 'father_id', 'mother_id', *CLAN_SOURCE_FIELDS)
    )


def clan_marriage_pairs(clan_id):
    return list(
        Marriage.objects.filter(husband__clan_id=clan_id, husband__is_deleted=False, wife__is_deleted=False)
        .values_list('husband_id', 'wife_id', 'status')
    )
