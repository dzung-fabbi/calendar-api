"""Reads for the personal family API (`/v1/family`).

A whole family is < 500 rows (spec §1), so every request loads it entirely:
`load_graph` is exactly TWO queries (persons, spouse links) regardless of size,
and every derived relation is computed from those rows in memory by
`services.family_graph.FamilyGraph`. There is deliberately no per-person
query helper for relations -- one loaded graph answers everything.
"""

from giapha.models import Family, FamilyPerson, FamilySpouse
from giapha.services.family_graph import FamilyGraph

PERSON_ROW_FIELDS = (
    'id', 'name', 'gender', 'deceased',
    'father_id', 'mother_id', 'father_rel', 'mother_rel',
    'solar_birth_date', 'birth_time', 'birth_order',
    'solar_death_date', 'death_time',
    'lunar_death_day', 'lunar_death_month', 'lunar_death_year', 'lunar_leap',
    'relationship', 'note', 'gio_event_id',
    'created_at', 'updated_at',
)


def family_for(user):
    """The user's one family, created on first touch. `select_related` is
    pointless here (`self_person_id` is all any caller reads)."""
    family, _ = Family.objects.get_or_create(user=user)
    return family


def person_rows(family_id):
    """Every person as a plain dict, in creation order (the app's default
    child sort when `birthOrder` is missing: `createdAt` then `id`)."""
    return list(
        FamilyPerson.objects.filter(family_id=family_id)
        .order_by('created_at', 'id')
        .values(*PERSON_ROW_FIELDS)
    )


def spouse_rows(family_id):
    return list(
        FamilySpouse.objects.filter(family_id=family_id)
        .values('person_a_id', 'person_b_id', 'type')
    )


def load_graph(family_id):
    """`(person_rows, spouse_rows, FamilyGraph)` -- the two queries every
    `/v1/family` request pays, and nothing else."""
    persons = person_rows(family_id)
    spouses = spouse_rows(family_id)
    return persons, spouses, FamilyGraph(persons, spouses)


def get_person_or_none(family_id, person_id):
    return FamilyPerson.objects.filter(family_id=family_id, id=person_id).first()
