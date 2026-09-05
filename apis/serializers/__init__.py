"""Serializer package. Re-exported flat so `from apis.serializers import X` works."""

from apis.serializers.account import UserSerializer
from apis.serializers.almanac import (
    HiepKySerializer,
    HourInDaySerializer,
    QuyNhanSerializer,
    TietKhiSerializer,
    TuDaiCatThoiSerializer,
)
from apis.serializers.booking import (
    AppointmentDateSerializer,
    BankSerializer,
    BookCalendarSerializer,
)
from apis.serializers.site_config import (
    DateConfigSerializer,
    DirectionConfigSerializer,
    HoursConfigSerializer,
)
from apis.serializers.stars import SaoSerializer, named_star_payload, star_payload
from apis.serializers.than_sat import (
    SaoMonth1Serializer,
    SaoMonth2Serializer,
    SaoMonth3Serializer,
    SaoMonth4Serializer,
    SaoMonth5Serializer,
    SaoMonth6Serializer,
    SaoMonth7Serializer,
    SaoMonth8Serializer,
    SaoMonth9Serializer,
    SaoMonth10Serializer,
    SaoMonth11Serializer,
    SaoMonth12Serializer,
    ThanSatByMonthSerializer,
    ThanSatByYearSerializer,
    ThanSatYearSaoSerializer,
)

__all__ = [
    'AppointmentDateSerializer', 'BankSerializer', 'BookCalendarSerializer',
    'DateConfigSerializer', 'DirectionConfigSerializer', 'HiepKySerializer',
    'HourInDaySerializer', 'HoursConfigSerializer', 'QuyNhanSerializer',
    'SaoSerializer', 'ThanSatByMonthSerializer', 'ThanSatByYearSerializer',
    'ThanSatYearSaoSerializer', 'TietKhiSerializer', 'TuDaiCatThoiSerializer',
    'UserSerializer', 'named_star_payload', 'star_payload',
] + ['SaoMonth{}Serializer'.format(i) for i in range(1, 13)]
