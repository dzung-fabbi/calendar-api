from django.urls import path
from .views import *

urlpatterns = [
  path("home", TestAPIView.as_view(), name="home"),
]
