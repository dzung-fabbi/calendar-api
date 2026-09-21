"""Is a clan person dead? -- pure, one rule for the member-facing API.

`da_mat` (explicit flag) OR any recorded death marker. Deliberately wider
than the `lich-gio` rule (which needs lunar day AND month to schedule a giỗ)
and than the public page's `_is_living` (which must fail closed).
"""


def is_deceased(person):
    """`person`: a Person instance or a row dict with the same keys."""
    get = person.get if isinstance(person, dict) else (lambda key: getattr(person, key))
    return bool(get('da_mat') or get('death_solar') or get('death_lunar_day') or get('death_lunar_month'))
