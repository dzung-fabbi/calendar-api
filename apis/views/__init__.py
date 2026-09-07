"""View package. Re-exported flat so `apis/urls.py` keeps its short imports."""

from apis.views.account import ConfigAPIView, UserAPIView
from apis.views.almanac import CalendarAPIView, HomeAPIView, TietkhiAPIView
from apis.views.auth_password_change import ChangePasswordAPIView
from apis.views.auth_password_reset import (
    ForgotPasswordAPIView,
    ResetPasswordAPIView,
    VerifyOtpAPIView,
)
from apis.views.auth_register import RegisterAPIView
from apis.views.booking import (
    AppointmentDateAPIView,
    BankAPIView,
    BookCalendarAPIView,
)
from apis.views.good_day import DateGoodByWorkAPIView
from apis.views.numerology import SoHocAPIView
from apis.views.than_sat import ThanSatAPIView

__all__ = [
    'AppointmentDateAPIView',
    'BankAPIView',
    'BookCalendarAPIView',
    'CalendarAPIView',
    'ChangePasswordAPIView',
    'ConfigAPIView',
    'DateGoodByWorkAPIView',
    'ForgotPasswordAPIView',
    'HomeAPIView',
    'RegisterAPIView',
    'ResetPasswordAPIView',
    'SoHocAPIView',
    'ThanSatAPIView',
    'TietkhiAPIView',
    'UserAPIView',
    'VerifyOtpAPIView',
]
