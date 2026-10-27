"""Output shape of a `Person` for the personal family API (spec §3.1).

Plain functions over the row dicts `selectors.family.person_rows` returns --
no DRF serializer, for the same reason `serializers/tree.py` is a passthrough:
the rows already carry the right values, and a per-field DRF pass would only
add latency. This is the ONE place the wire shape is declared; the tests
assert the key set.
"""

from giapha.services.family_clan_field_map import CLAN_SOURCE_FIELDS, clan_to_family
from giapha.services.family_dates import epoch_ms, format_date

PERSON_KEYS = (
    'id', 'name', 'gender', 'deceased',
    'fatherId', 'motherId', 'fatherRel', 'motherRel', 'spouses',
    'solarBirthDate', 'birthTime', 'birthOrder',
    'solarDeathDate', 'deathTime',
    'lunarDeathDay', 'lunarDeathMonth', 'lunarDeathYear', 'lunarLeap',
    'relationship', 'note', 'phone', 'education', 'occupation', 'gioEventId',
    'createdAt', 'updatedAt', 'linked',
)


def id_str(value):
    return str(value) if value is not None else None


def spouses_by_person(spouse_rows):
    """`{person_id: [{'id', 'type'}, ...]}` from the stored one-row-per-pair
    links, expanded to both directions and sorted for a stable response."""
    out = {}
    for row in spouse_rows:
        a, b, kind = row['person_a_id'], row['person_b_id'], row['type']
        out.setdefault(a, []).append({'id': id_str(b), 'type': kind})
        out.setdefault(b, []).append({'id': id_str(a), 'type': kind})
    for links in out.values():
        links.sort(key=lambda link: link['id'])
    return out


def person_to_dict(row, spouses, linked=False):
    """`row`: one dict from `person_rows`. `spouses`: that person's list from
    `spouses_by_person` (or `[]`). `linked`: shared fields in `row` were
    overlaid from a clan person (`overlay_links`)."""
    return {
        'id': id_str(row['id']),
        'name': row['name'],
        'gender': row['gender'],
        'deceased': row['deceased'],
        'fatherId': id_str(row['father_id']),
        'motherId': id_str(row['mother_id']),
        'fatherRel': row['father_rel'] or None,
        'motherRel': row['mother_rel'] or None,
        'spouses': list(spouses),
        'solarBirthDate': format_date(row['solar_birth_date']),
        'birthTime': row['birth_time'] or None,
        'birthOrder': row['birth_order'],
        'solarDeathDate': format_date(row['solar_death_date']),
        'deathTime': row['death_time'] or None,
        'lunarDeathDay': row['lunar_death_day'],
        'lunarDeathMonth': row['lunar_death_month'],
        'lunarDeathYear': row['lunar_death_year'],
        'lunarLeap': row['lunar_leap'],
        'relationship': row['relationship'] or None,
        'note': row['note'] or None,
        'phone': row['phone'] or None,
        'education': row['education'] or None,
        'occupation': row['occupation'] or None,
        'gioEventId': row['gio_event_id'] or None,
        'createdAt': epoch_ms(row['created_at']),
        'updatedAt': epoch_ms(row['updated_at']),
        'linked': linked,
    }


def overlay_links(person_rows, link_rows):
    """Replace the shared fields of every linked person with the clan's
    current values (spec §14.1: read through, never copied). A person linked
    into several clans reads from the OLDEST link. Returns `(rows, linked_ids)`.
    """
    source = {}
    for link in link_rows:
        source.setdefault(link['family_person_id'], link)
    rows = []
    for row in person_rows:
        link = source.get(row['id'])
        if link is not None:
            clan_values = {field: link['clan_person__' + field] for field in CLAN_SOURCE_FIELDS}
            row = dict(row, **clan_to_family(clan_values))
        rows.append(row)
    return rows, set(source)


def links_payload(link_rows):
    return [
        {'id': link['id'], 'personId': id_str(link['family_person_id']), 'clanId': link['clan_id'],
         'clanPersonId': link['clan_person_id'], 'clanName': link['clan__ten_ho']}
        for link in link_rows
    ]


def persons_payload(person_rows, spouse_rows, link_rows=()):
    """The `persons[]` array every read and every mutation response carries."""
    rows, linked_ids = overlay_links(person_rows, link_rows)
    links = spouses_by_person(spouse_rows)
    return [person_to_dict(row, links.get(row['id'], []), row['id'] in linked_ids) for row in rows]
