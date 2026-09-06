"""Row-shaping for `GET /public/{slug}/persons/{pid}` (phase 9).

Same whitelist discipline as `services.public_tree`: only ever reads keys
that `selectors.public.public_person_row`'s matching liveness branch
actually selected. The only non-pure part is `_photo_url`, which calls
`services.storage` (network-adjacent, no ORM) -- allowed under
`docs/code-standards.md` ("no ORM" is the rule, not "no I/O"), same as
`services.fcm`.
"""

import logging

from giapha.services import storage
from giapha.services.public_name import public_display_name

logger = logging.getLogger(__name__)


def _photo_url(photo_key):
    """Mirrors `serializers.person.PersonReadSerializer.get_photo_url`:
    `None` whenever there's nothing to show, storage isn't configured, or
    presigning itself fails. A broken/unconfigured photo link must not turn
    an otherwise-fine public person read into a 500 -- this is the ONLY
    place in this module with a broad `except`, deliberately, matching the
    precedent it mirrors.
    """
    if not photo_key:
        return None
    if not storage.is_configured():
        return None
    try:
        return storage.presign_get(photo_key)
    except Exception:
        logger.warning('Không tạo được photo_url công khai cho key=%s', photo_key, exc_info=True)
        return None


def public_person_payload(row, *, is_living, hide_living_details):
    """`row` came from either the LIVING or the DEAD branch of
    `selectors.public.public_person_row` -- see that function's docstring
    for why a living row has no `ten_huy`/`ten_tu`/`ten_hieu`/`thuy_hieu`/
    dates/`que_quan`/`nghe_nghiep`/`tieu_su`/`photo_key` to read at all.
    `mo_phan_*` never appears here either, living or dead.
    """
    if is_living:
        return {
            'id': row['id'],
            'ho_ten': public_display_name(
                row['ho_ten'], is_living=True, hide_living_details=hide_living_details,
            ),
            'ten_huy': None, 'ten_tu': None, 'ten_hieu': None, 'thuy_hieu': None,
            'generation': row['generation'],
            'branch': row['branch'],
            'is_truong': row['is_truong'],
            'birth_order': row['birth_order'],
            'is_living': True,
            'birth_year': None, 'death_year': None, 'death_lunar': None,
            'que_quan': None, 'nghe_nghiep': None, 'tieu_su': None,
            'photo_url': None,
        }

    birth_solar = row['birth_solar']
    death_solar = row['death_solar']
    death_lunar_day = row['death_lunar_day']
    death_lunar_month = row['death_lunar_month']
    return {
        'id': row['id'],
        'ho_ten': row['ho_ten'],
        'ten_huy': row['ten_huy'],
        'ten_tu': row['ten_tu'],
        'ten_hieu': row['ten_hieu'],
        'thuy_hieu': row['thuy_hieu'],
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
        'que_quan': row['que_quan'],
        'nghe_nghiep': row['nghe_nghiep'],
        'tieu_su': row['tieu_su'],
        'photo_url': _photo_url(row['photo_key']),
    }
