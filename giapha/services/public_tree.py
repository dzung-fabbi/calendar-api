"""Pure row-shaping for the public gia phả tree (phase 9).

No ORM, no `request` -- takes plain `.values()` row dicts, same convention
as `services.tree`. The whitelist lives HERE, not in the serializer: even if
`serializers.public.PublicTreeNodeSerializer` were ever mis-edited to add a
field, this function is what decides what actually goes into the dict it
serializes, and it only reads `row[...]` keys that
`selectors.public.public_tree_payload` actually selected for that row's
liveness branch.
"""

from giapha.services.public_name import public_display_name


def public_parent_edges_from_rows(rows):
    """Public counterpart of `services.tree.parent_edges_from_rows`.

    Exists solely to DROP `kind`. The internal version copies
    `row['parent_kind']` (`ruot`/`nuoi`/`ke`) into every edge, which on the
    public surface would publish that a living person is adopted or a
    step-child -- a field absent from the phase-9 whitelist table, and in
    Vietnamese family context genuinely sensitive. `parent_kind` is no
    longer selected for public rows at all (see
    `selectors.public._PUBLIC_*_TREE_FIELDS`), so reusing the internal
    builder would now raise `KeyError` rather than leak -- but the point is
    that a public edge should never have carried it in the first place.

    Same truncation behaviour as the internal version: a parent outside
    `rows` is omitted rather than pointing at a node the client never got.
    """
    included_ids = {row['id'] for row in rows}
    edges = []
    for row in rows:
        child_id = row['id']
        for parent_id, role in ((row['father_id'], 'father'), (row['mother_id'], 'mother')):
            if parent_id is not None and parent_id in included_ids:
                edges.append({'type': 'parent', 'from': parent_id, 'to': child_id, 'role': role})
    return edges


def public_node_from_row(row, *, is_living, hide_living_details):
    """One `nodes[]` entry. `row` came from either the LIVING or the DEAD
    branch of `selectors.public.public_tree_payload` -- a living row has NO
    `ten_huy`/birth or death columns/`photo_key` to read at all (they were
    never selected at the SQL layer), so this function must not touch those
    keys when `is_living` is True; it returns fixed `None`/`False` values
    for them instead.

    `mo_phan_*` never appears here, for anyone -- there is no branch, living
    or dead, that reads it (phase-9 spec: grave coordinates are never
    public).
    """
    if is_living:
        return {
            'id': row['id'],
            'ho_ten': public_display_name(
                row['ho_ten'], is_living=True, hide_living_details=hide_living_details,
            ),
            'ten_huy': None,
            'generation': row['generation'],
            'branch': row['branch'],
            'is_truong': row['is_truong'],
            'birth_order': row['birth_order'],
            'is_living': True,
            'birth_year': None,
            'death_year': None,
            'death_lunar': None,
            # Never True for a living person -- withholding just the URL
            # is not enough (phase-9 spec explicitly calls this out): the
            # boolean itself must not confirm a living person has a photo
            # on file.
            'has_photo': False,
        }

    birth_solar = row['birth_solar']
    death_solar = row['death_solar']
    death_lunar_day = row['death_lunar_day']
    death_lunar_month = row['death_lunar_month']
    return {
        'id': row['id'],
        'ho_ten': row['ho_ten'],
        'ten_huy': row['ten_huy'],
        'generation': row['generation'],
        'branch': row['branch'],
        'is_truong': row['is_truong'],
        'birth_order': row['birth_order'],
        'is_living': False,
        'birth_year': birth_solar.year if birth_solar is not None else None,
        'death_year': death_solar.year if death_solar is not None else None,
        'death_lunar': (
            {'day': death_lunar_day, 'month': death_lunar_month, 'leap': row['death_lunar_leap']}
            if death_lunar_day is not None and death_lunar_month is not None
            else None
        ),
        'has_photo': bool(row['photo_key']),
    }
