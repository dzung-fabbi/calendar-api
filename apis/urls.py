from django.urls import path
from .views import *

urlpatterns = [
  path("home", HomeAPIView.as_view(), name="home"),
  path("tiet-khi", TietkhiAPIView.as_view(), name="tiet_khi"),
  path("than-sat", ThanSatAPIView.as_view(), name="than_sat"),
  path("so-hoc", SoHocAPIView.as_view(), name="so_hoc"),
  path("calendar", CalendarAPIView.as_view(), name="calendar"),
]
