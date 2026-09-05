"""Can chi (sexagenary cycle) naming for a solar date.

Deliberately a copy of the three-line `can_chi_for_date` in
`apis/services/can_chi.py` rather than an import. Two reasons, in order:

1. `giapha` does not import from `apis` -- the same package boundary that made
   `giapha/exceptions.py` a copy of `apis/exceptions.py`. Phases 1-4 hold that
   line everywhere; one exception would quietly become the precedent for more.
2. `apis/services/can_chi.py` imports `lunarcalendar` at module level, i.e.
   the CHINESE UTC+8 calendar. Importing it here would drag the very library
   `giapha.services.vn_lunar` exists to avoid into the giỗ code path.

The cost of the copy is 10 lines that can never drift, because the can-chi
cycle is a fixed 60-day rotation off a fixed epoch. If that ever stops being
true, both copies are wrong in the same way anyway.
"""

import datetime as dt

CAN = ['Giáp', 'Ất', 'Bính', 'Đinh', 'Mậu', 'Kỷ', 'Canh', 'Tân', 'Nhâm', 'Quý']
CHI = ['Tý', 'Sửu', 'Dần', 'Mão', 'Thìn', 'Tỵ', 'Ngọ', 'Mùi', 'Thân', 'Dậu', 'Tuất', 'Hợi']

# 1984-01-31 is a Giáp Tý day, the start of a 60-day cycle.
GIAP_TY_EPOCH = dt.date(1984, 1, 31)


def can_chi_for_date(solar_date):
    """Can-chi name of a solar date, e.g. 'Giáp Tý'."""
    days = (solar_date - GIAP_TY_EPOCH).days
    return '{} {}'.format(CAN[days % 10], CHI[days % 12])
