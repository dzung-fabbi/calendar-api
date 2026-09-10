"""Output shape of a `Person` for the personal family API (spec §3.1).

Plain functions over the row dicts `selectors.family.person_rows` returns --
no DRF serializer, for the same reason `serializers/tree.py` is a passthrough:
the rows already carry the right values, and a per-field DRF pass would only
add latency. This is the ONE place the wire shape is declared; the tests
assert the key set.
"""

from giapha.services.family_dates import epoch_ms, format_date

PERSON_KEYS = (
    'id', 'name', 'gender', 'deceased',
    'fatherId', 'motherId', 'fatherRel', 'motherRel', 'spouses',
    'solarBirthDate', 'birthTime', 'birthOrder',
    'solarDeathDate', 'deathTime',
    'lunarDeathDay', 'lunarDeathMonth', 'lunarDeathYear', 'lunarLeap',
    'relationship', 'note', 'gioEventId',
    'createdAt', 'updatedAt',
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


def person_to_dict(row, spouses):
    """`row`: one dict from `person_rows`. `spouses`: that person's list from
    `spouses_by_person` (or `[]`)."""
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
        'gioEventId': row['gio_event_id'] or None,
        'createdAt': epoch_ms(row['created_at']),
        'updatedAt': epoch_ms(row['updated_at']),
    }


def persons_payload(person_rows, spouse_rows):
    """The `persons[]` array every read and every mutation response carries."""
    links = spouses_by_person(spouse_rows)
    return [person_to_dict(row, links.get(row['id'], [])) for row in person_rows]
