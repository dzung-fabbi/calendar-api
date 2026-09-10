"""Merge a validated `PersonDraft` onto the current row and derive what the
server owns (spec §2.4). Pure: dicts in, dict out.

`solar_death_date` is DERIVED, never trusted from the client, whenever the
lunar day+month+year are all known after the merge. When they are not, the
client-supplied value (if any) is kept -- an old record may carry only a solar
date, and the app tolerates that.
"""

from giapha.services.family_dates import derive_solar_death

# Optional text fields where the app sends "" to mean "cleared".
_TEXT_FIELDS = ('birth_time', 'death_time', 'relationship', 'note', 'gio_event_id')
_LUNAR_FIELDS = ('lunar_death_day', 'lunar_death_month', 'lunar_death_year', 'lunar_leap')


def finalize_draft(current, incoming):
    """`current`: the row's present values (`{}` for a create). `incoming`:
    `PersonDraftSerializer.validated_data` (snake_case keys, partial for a
    PATCH). Returns the fields to write."""
    draft = dict(incoming)
    for field in _TEXT_FIELDS:
        if field in draft and draft[field] == '':
            draft[field] = None

    merged = dict(current)
    merged.update(draft)
    lunar = [merged.get(field) for field in _LUNAR_FIELDS]
    derived = derive_solar_death(*lunar)
    if derived is not None:
        draft['solar_death_date'] = derived
    elif any(field in draft for field in _LUNAR_FIELDS) and 'solar_death_date' not in draft:
        # Lunar fields changed to an incomplete/invalid set: a previously
        # derived solar date would now be stale, so drop it -- unless the
        # client explicitly sent one in the same request.
        draft['solar_death_date'] = None
    return draft
