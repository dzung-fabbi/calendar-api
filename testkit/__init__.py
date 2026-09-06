"""Top-level test-support package shared by ``apis`` and ``giapha``.

Lives outside both app packages on purpose: ``giapha`` must not import from
``apis`` (see ``giapha/exceptions.py``'s module docstring for the same rule
applied to its own exception classes), so shared test-only logic that both
apps need cannot live inside either app's ``tests/`` package. It also must
not be listed in ``INSTALLED_APPS`` and contains no ``test_*.py`` modules, so
``manage.py test apis giapha`` (which only discovers within the named app
labels) never touches it and a bare ``manage.py test`` would not pick it up
as a test module either.
"""
