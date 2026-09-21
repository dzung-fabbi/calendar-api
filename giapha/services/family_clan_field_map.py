"""The ONE mapping between a personal-tree person (`FamilyPerson`) and a clan
person (`Person`) -- spec §14.2. Pure, no ORM.

Shared fields (read from the clan while linked):

    FamilyPerson          Person (clan)
    name               <-> ho_ten
    gender             <-> gioi_tinh      male/female/unknown <-> nam/nu/khac
    deceased           <-> da_mat         (clan side: da_mat OR any death marker)
    solar_birth_date   <-> birth_solar
    solar_death_date   <-> death_solar
    lunar_death_day    <-> death_lunar_day
    lunar_death_month  <-> death_lunar_month
    lunar_leap         <-> death_lunar_leap
    lunar_death_year    -> derived from death_solar through `vn_lunar`

Everything else is private to its side (birth/death time, relationship, note,
gioEventId, birthOrder on the family side; names huý/tự/hiệu, photo, grave,
biography, generation, branch on the clan side).
"""

from giapha.services import vn_lunar
from giapha.services.person_status import is_deceased

SHARED_FAMILY_FIELDS = (
    'name', 'gender', 'deceased', 'solar_birth_date', 'solar_death_date',
    'lunar_death_day', 'lunar_death_month', 'lunar_death_year', 'lunar_leap',
)
# Clan columns `clan_to_family` reads (also the `.values()` list for bulk reads).
CLAN_SOURCE_FIELDS = (
    'ho_ten', 'gioi_tinh', 'da_mat', 'birth_solar', 'death_solar',
    'death_lunar_day', 'death_lunar_month', 'death_lunar_leap',
)

_GENDER_TO_FAMILY = {'nam': 'male', 'nu': 'female', 'khac': 'unknown'}
_GENDER_TO_CLAN = {value: key for key, value in _GENDER_TO_FAMILY.items()}


def _get(source, key):
    return source.get(key) if isinstance(source, dict) else getattr(source, key)


def _lunar_year_of(solar_date):
    if solar_date is None or not (vn_lunar.MIN_YEAR <= solar_date.year <= vn_lunar.MAX_YEAR):
        return None
    return vn_lunar.solar_to_lunar(solar_date.day, solar_date.month, solar_date.year)[2]


def clan_to_family(person):
    """Shared-field dict (FamilyPerson field names) from a clan Person or a
    `.values(*CLAN_SOURCE_FIELDS)` row."""
    death_solar = _get(person, 'death_solar')
    return {
        'name': (_get(person, 'ho_ten') or '')[:60],
        'gender': _GENDER_TO_FAMILY.get(_get(person, 'gioi_tinh'), 'unknown'),
        'deceased': is_deceased({key: _get(person, key) for key in (
            'da_mat', 'death_solar', 'death_lunar_day', 'death_lunar_month')}),
        'solar_birth_date': _get(person, 'birth_solar'),
        'solar_death_date': death_solar,
        'lunar_death_day': _get(person, 'death_lunar_day'),
        'lunar_death_month': _get(person, 'death_lunar_month'),
        'lunar_death_year': _lunar_year_of(death_solar),
        'lunar_leap': bool(_get(person, 'death_lunar_leap')),
    }


def family_to_clan(fields):
    """Clan Person fields for the shared keys PRESENT in `fields` (FamilyPerson
    field names; partial input -> partial output). Private keys are ignored.
    """
    mapping = (
        ('name', 'ho_ten', lambda value: value),
        ('gender', 'gioi_tinh', lambda value: _GENDER_TO_CLAN.get(value, 'khac')),
        ('deceased', 'da_mat', bool),
        ('solar_birth_date', 'birth_solar', lambda value: value),
        ('solar_death_date', 'death_solar', lambda value: value),
        ('lunar_death_day', 'death_lunar_day', lambda value: value),
        ('lunar_death_month', 'death_lunar_month', lambda value: value),
        ('lunar_leap', 'death_lunar_leap', bool),
    )
    return {clan_key: convert(fields[family_key]) for family_key, clan_key, convert in mapping if family_key in fields}


def family_to_clan_payload(fields):
    """`family_to_clan` as JSON-ready input for `PersonWriteSerializer`
    (dates as ISO strings) -- what a change request stores."""
    out = family_to_clan(fields)
    for key in ('birth_solar', 'death_solar'):
        if out.get(key) is not None:
            out[key] = out[key].isoformat()
    return out
