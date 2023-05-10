from django.urls import path
from .views import *

urlpatterns = [
  path("home", HomeAPIView.as_view(), name="home"),
  path("tiet-khi", TietkhiAPIView.as_view(), name="tiet_khi"),
  path("than-sat", ThanSatAPIView.as_view(), name="than_sat"),
  path("so-hoc", SoHocAPIView.as_view(), name="so_hoc"),
  path("calendar", CalendarAPIView.as_view(), name="calendar"),
  path("get-date-good-by-work", DateGoodByWorkAPIView.as_view(), name="get_date_good_by_work"),
  path("book-calendar", BookCalendarAPIView.as_view(), name="book-calendar"),
  path("appointment-date", AppointmentDateAPIView.as_view(), name="appointment-date"),
]
