"""djangopj URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf.urls import url
from django.contrib import admin
from django.urls import path, include

from djangopj.auth_token_views import RevokeTokenView, TokenView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apis.urls')),
    path('api/gia-pha/', include('giapha.urls')),
    # Login and logout. `/?$` keeps the trailing slash OPTIONAL -- shipped
    # clients call `/auth/token` bare and must not start 404ing.
    url(r'^auth/token/?$', TokenView.as_view(), name='auth-token'),
    url(r'^auth/revoke-token/?$', RevokeTokenView.as_view(), name='auth-revoke-token'),
]
