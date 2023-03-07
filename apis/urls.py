from django.urls import path
from .views import *

urlpatterns = [
  path("home", HomeAPIView.as_view(), name="home"),
  path("tiet-khi", TietkhiAPIView.as_view(), name="tiet_khi"),
]
