from django.urls import path

from apis.views import (
    AppointmentDateAPIView,
    BankAPIView,
    BookCalendarAPIView,
    CalendarAPIView,
    ChangePasswordAPIView,
    ConfigAPIView,
    DateGoodByWorkAPIView,
    FileConfirmAPIView,
    FileUploadUrlAPIView,
    ForgotPasswordAPIView,
    HomeAPIView,
    RegisterAPIView,
    ResetPasswordAPIView,
    SoHocAPIView,
    ThanSatAPIView,
    TietkhiAPIView,
    UserAPIView,
    VerifyOtpAPIView,
)

urlpatterns = [
    path("home", HomeAPIView.as_view(), name="home"),
    path("tiet-khi", TietkhiAPIView.as_view(), name="tiet_khi"),
    path("than-sat", ThanSatAPIView.as_view(), name="than_sat"),
    path("so-hoc", SoHocAPIView.as_view(), name="so_hoc"),
    path("calendar", CalendarAPIView.as_view(), name="calendar"),
    path("get-date-good-by-work", DateGoodByWorkAPIView.as_view(), name="get_date_good_by_work"),
    path("book-calendar", BookCalendarAPIView.as_view(), name="book-calendar"),
    path("appointment-date", AppointmentDateAPIView.as_view(), name="appointment-date"),
    path("get-config", ConfigAPIView.as_view(), name="get-config"),
    path("get-bank", BankAPIView.as_view(), name="get-bank"),
    path("get-user", UserAPIView.as_view(), name="get-user"),
    # Same view as `get-user` above, under the name new clients should use.
    # `get-user` is GET-only in every shipped client and cannot be renamed;
    # rather than duplicate a view, both paths reach the one that now also
    # handles PATCH.
    path("me", UserAPIView.as_view(), name="me"),

    # Presigned S3/R2 upload for generic files. No bytes ever cross Django --
    # see `apis/services/storage.py` / `apis/views/file_upload.py`. Both are
    # AllowAny + throttled; read the file_upload module docstring before
    # widening either.
    path("files/upload-url", FileUploadUrlAPIView.as_view(), name="file-upload-url"),
    path("files/confirm", FileConfirmAPIView.as_view(), name="file-confirm"),

    # Account management. `/auth/token` and `/auth/revoke-token` (login and
    # logout, mounted in `djangopj/urls.py`) are deliberately NOT part of this
    # group -- shipped clients call them at the root and they stay there.
    path("auth/register", RegisterAPIView.as_view(), name="auth-register"),
    path(
        "auth/forgot-password",
        ForgotPasswordAPIView.as_view(),
        name="auth-forgot-password",
    ),
    path("auth/verify-otp", VerifyOtpAPIView.as_view(), name="auth-verify-otp"),
    path(
        "auth/reset-password",
        ResetPasswordAPIView.as_view(),
        name="auth-reset-password",
    ),
    path(
        "auth/change-password",
        ChangePasswordAPIView.as_view(),
        name="auth-change-password",
    ),
]
