"""Model package.

Re-exports every model so `from apis.models import X` keeps working -- the 71
existing migrations and the rest of the app depend on that flat namespace.
The choice tuples are re-exported too, since the migrations reference them.
"""

from apis.models.almanac import HiepKy, HourInDay, SaoHiepKy, TietKhi
from apis.models.auspicious_hours import QuyNhan, TuDaiCatThoi, TuDaiCatThoiSao
from apis.models.booking import (
    AppointmentDate,
    BankConfig,
    BankTransaction,
    BookCalendar,
    UserProfile,
)
from apis.models.choices import (
    AM_DUONG,
    CALENDAR,
    HOURS,
    STATUS_TRANSACTION,
    can_ngay,
    cung_son,
    direction,
    good_ugly_start,
    is_mountain,
    lunar_day,
    month,
    tiet_khi,
)
from apis.models.hour_stars import (
    SaoHour1,
    SaoHour2,
    SaoHour3,
    SaoHour4,
    SaoHour5,
    SaoHour6,
    SaoHour7,
    SaoHour8,
    SaoHour9,
    SaoHour10,
    SaoHour11,
    SaoHour12,
)
from apis.models.month_stars import (
    SaoMonth1,
    SaoMonth2,
    SaoMonth3,
    SaoMonth4,
    SaoMonth5,
    SaoMonth6,
    SaoMonth7,
    SaoMonth8,
    SaoMonth9,
    SaoMonth10,
    SaoMonth11,
    SaoMonth12,
    SaoMonthBase,
)
from apis.models.password_reset import PasswordResetCode
from apis.models.refresh_token import RefreshToken
from apis.models.site_config import DateConfig, DirectionConfig, HoursConfig
from apis.models.stars import CategoryStars, Sao
from apis.models.than_sat import (
    ItemBase,
    ThanSatByMonth,
    ThanSatByYear,
    ThanSatByYearSao,
)

# Ordered groups the serializers, views and admin iterate over instead of
# repeating twelve near-identical blocks.
SAO_HOUR_MODELS = (
    SaoHour1, SaoHour2, SaoHour3, SaoHour4, SaoHour5, SaoHour6,
    SaoHour7, SaoHour8, SaoHour9, SaoHour10, SaoHour11, SaoHour12,
)

SAO_MONTH_MODELS = (
    SaoMonth1, SaoMonth2, SaoMonth3, SaoMonth4, SaoMonth5, SaoMonth6,
    SaoMonth7, SaoMonth8, SaoMonth9, SaoMonth10, SaoMonth11, SaoMonth12,
)

__all__ = [
    'AM_DUONG', 'CALENDAR', 'HOURS', 'STATUS_TRANSACTION',
    'AppointmentDate', 'BankConfig', 'BankTransaction', 'BookCalendar',
    'CategoryStars', 'DateConfig', 'DirectionConfig', 'HiepKy', 'HourInDay',
    'HoursConfig', 'ItemBase', 'PasswordResetCode', 'QuyNhan', 'RefreshToken', 'Sao',
    'SaoHiepKy', 'SaoMonthBase',
    'ThanSatByMonth', 'ThanSatByYear', 'ThanSatByYearSao', 'TietKhi',
    'TuDaiCatThoi', 'TuDaiCatThoiSao', 'UserProfile',
    'SAO_HOUR_MODELS', 'SAO_MONTH_MODELS',
    'can_ngay', 'cung_son', 'direction', 'good_ugly_start', 'is_mountain',
    'lunar_day', 'month', 'tiet_khi',
] + [
    'SaoHour{}'.format(index) for index in range(1, 13)
] + [
    'SaoMonth{}'.format(index) for index in range(1, 13)
]
