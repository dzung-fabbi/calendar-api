"""Admin package.

Importing the submodules is what registers the ModelAdmins; Django imports
this package for us via `django.contrib.admin.autodiscover`.
"""

from django.contrib import admin

from apis.admin import almanac, site_config, than_sat  # noqa: F401

admin.site.site_header = 'Thiên văn lịch pháp'
