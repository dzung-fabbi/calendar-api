"""Revision snapshot helpers for Person -- pure, no ORM.

`snapshot()` turns a Person into a JSON string and `restore()` puts one back
onto an instance in memory; neither touches the database. The row-writing
counterpart lives in `selectors/revision.py::record`, keeping this module
importable without a database (see docs/code-standards.md).
"""

import datetime
import decimal
import json

# `id` is the row's own identity, not content to restore; created_at/updated_at
# are bookkeeping about the record itself, not its genealogical content --
# restoring them would make every restore touch fields nobody asked to change.
# `is_deleted` is excluded so `POST /restore` can never silently undelete a
# soft-deleted person -- restoring genealogical content and undeleting are
# two different actions, and this module only ever does the former.
# `clan_id` is excluded too: no endpoint ever moves a person between clans,
# so restoring it serves no purpose and only widens the field for no gain.
_EXCLUDED_FIELDS = frozenset({'id', 'created_at', 'updated_at', 'is_deleted', 'clan_id'})


def _to_json_value(value):
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    return value


def snapshot(person):
    """JSON string of every Person field except `_EXCLUDED_FIELDS`, keyed by
    attribute name (`father_id`, not `father`) so `restore()` can `setattr`
    it straight back without touching a related object.
    """
    data = {}
    for field in person._meta.fields:
        if field.name in _EXCLUDED_FIELDS:
            continue
        data[field.attname] = _to_json_value(getattr(person, field.attname))
    return json.dumps(data)


def restore(person, payload_json):
    """Set every field from a previously recorded snapshot back onto
    `person` (in memory -- caller still has to `.save()`). Django's field
    `to_python`/`get_prep_value` handles the string -> date/Decimal
    conversion at save time, so no manual parsing is needed here.
    """
    data = json.loads(payload_json)
    for attname, value in data.items():
        setattr(person, attname, value)
    return person
