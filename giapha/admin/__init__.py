"""Admin package.

Importing the submodules is what registers the ModelAdmins; Django imports
this package for us via `django.contrib.admin.autodiscover`.
"""

from giapha.admin import clan, person  # noqa: F401
