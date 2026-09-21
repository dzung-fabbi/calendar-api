"""Field normalisation for `PUT /v1/family/import` -- pure, no ORM.

Old on-device data cannot be fixed by the user in bulk, so a bad FIELD never
rejects a person: it is repaired (trimmed, nulled, defaulted) and reported as
a warning `{personId, field, message}`. Only the shape of the whole request
(list, size, ids) is a hard error -- see `serializers.family_import`.

Output keys are `FamilyPerson` model fields (snake_case); edges are handled
separately by `services.family_import`.
"""

import datetime as dt

from giapha.services.family_dates import DATE_FORMAT, TIME_RE
from giapha.services.family_draft import finalize_draft

UNNAMED = 'Chưa đặt tên'
GENDERS = ('male', 'female', 'unknown')
_TEXT_LIMITS = (('relationship', 'relationship', 24), ('note', 'note', 200), ('gioEventId', 'gio_event_id', 64))


class _Collector:
    def __init__(self, person_id):
        self.person_id = person_id
        self.items = []

    def add(self, field, message):
        self.items.append({'personId': self.person_id, 'field': field, 'message': message})


def _int_in(value, low, high):
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if low <= value <= high else None


def _date(raw, field, warn):
    if raw in (None, ''):
        return None
    try:
        return dt.datetime.strptime(str(raw), DATE_FORMAT).date()
    except ValueError:
        warn.add(field, 'Ngày không đúng định dạng DD-MM-YYYY, đã bỏ.')
        return None


def _time(raw, field, warn):
    if raw in (None, ''):
        return None
    if isinstance(raw, str) and TIME_RE.match(raw):
        return raw
    warn.add(field, 'Giờ không đúng định dạng HH:mm, đã bỏ.')
    return None


def _epoch(raw):
    """Client `createdAt`/`updatedAt` (epoch ms) -> aware UTC datetime, or None."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw <= 0:
        return None
    try:
        return dt.datetime.fromtimestamp(raw / 1000.0, tz=dt.timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _name(raw, warn):
    name = raw.strip() if isinstance(raw, str) else ''
    if not name:
        warn.add('name', 'Tên trống, đã đặt "{}".'.format(UNNAMED))
        return UNNAMED
    if len(name) > 60:
        warn.add('name', 'Tên dài quá 60 ký tự, đã cắt bớt.')
        return name[:60]
    return name


def _lunar(raw, fields, warn):
    for wire, model_field, low, high, label in (
        ('lunarDeathDay', 'lunar_death_day', 1, 30, 'Ngày mất âm lịch'),
        ('lunarDeathMonth', 'lunar_death_month', 1, 12, 'Tháng mất âm lịch'),
    ):
        value = raw.get(wire)
        fields[model_field] = _int_in(value, low, high)
        if value is not None and fields[model_field] is None:
            warn.add(wire, '{} ngoài khoảng {}-{}, đã bỏ.'.format(label, low, high))
    year = raw.get('lunarDeathYear')
    fields['lunar_death_year'] = year if isinstance(year, int) and not isinstance(year, bool) else None
    leap = raw.get('lunarLeap')
    fields['lunar_leap'] = leap if isinstance(leap, bool) else None


def normalize_person(raw):
    """`(model_fields, warnings)` for one client `Person` dict."""
    warn = _Collector(raw.get('id'))
    gender = raw.get('gender')
    if gender not in GENDERS:
        if gender is not None:
            warn.add('gender', 'Giới tính không hợp lệ, đã đặt "unknown".')
        gender = 'unknown'

    fields = {
        'name': _name(raw.get('name'), warn),
        'gender': gender,
        'deceased': raw.get('deceased') is True,
        'solar_birth_date': _date(raw.get('solarBirthDate'), 'solarBirthDate', warn),
        'birth_time': _time(raw.get('birthTime'), 'birthTime', warn),
        'birth_order': _int_in(raw.get('birthOrder'), 1, 10 ** 6),
        'solar_death_date': _date(raw.get('solarDeathDate'), 'solarDeathDate', warn),
        'death_time': _time(raw.get('deathTime'), 'deathTime', warn),
    }
    _lunar(raw, fields, warn)
    for wire, model_field, limit in _TEXT_LIMITS:
        value = raw.get(wire)
        value = value.strip() if isinstance(value, str) else None
        if value and len(value) > limit:
            warn.add(wire, 'Dài quá {} ký tự, đã cắt bớt.'.format(limit))
            value = value[:limit]
        fields[model_field] = value or None

    # Same server-owned derivation as a normal create (spec §2.4).
    fields = finalize_draft({}, fields)
    fields['created_at'] = _epoch(raw.get('createdAt'))
    fields['updated_at'] = _epoch(raw.get('updatedAt')) or fields['created_at']
    return fields, warn.items
