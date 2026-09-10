"""djangopj URL Configuration.

Login, refresh and logout live under `apis/` (`/api/auth/login|refresh|logout`,
see `apis/views/auth_login.py`). The former root-level `/auth/token` and
`/auth/revoke-token` (django-oauth-toolkit) were removed on 2026-09-10 and
answer 404 by design.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apis.urls')),
    path('api/gia-pha/', include('giapha.urls')),
]
