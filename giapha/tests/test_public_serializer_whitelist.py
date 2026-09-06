"""Static/mutation guards for `serializers/public.py`'s whitelist
discipline -- split out of `test_public_security.py` once that file
crossed the 200-line ceiling.
"""

import re
from pathlib import Path

from django.test import TestCase


class SerializerSourceWhitelistTests(TestCase):
    """Static check: the public serializer module must never regress to a
    blacklist mechanism.
    """

    def test_public_serializer_source_has_no_blacklist_shortcuts(self):
        path = Path(__file__).resolve().parent.parent / 'serializers' / 'public.py'
        source = path.read_text(encoding='utf-8')

        all_fields_pattern = re.compile(r"""fields\s*=\s*['"]__all__['"]""")
        exclude_kwarg_pattern = re.compile(r'\bexclude\s*=')

        self.assertIsNone(
            all_fields_pattern.search(source),
            "serializers/public.py must never declare fields = '__all__'",
        )
        self.assertIsNone(
            exclude_kwarg_pattern.search(source),
            'serializers/public.py must never declare an `exclude` field list',
        )


class SerializerMutationDemonstrationTests(TestCase):
    """NOT a permanent regression test -- see the module docstring of
    `test_public_security.py`. This class exists so the mutation exercise
    the phase-9 spec's Acceptance section asks for ("add a sensitive
    field, confirm a test fails, then revert") is reproducible: temporarily
    add, e.g., `mo_phan_lat = serializers.CharField(allow_null=True,
    required=False)` to `PublicTreeNodeSerializer` and re-run
    `test_public_security.PublicTreeAndDetailFieldWhitelistTests.
    test_dead_person_grave_coordinates_absent_from_tree_node` /
    `test_tree_node_key_set_is_exactly_the_whitelist` -- both fail the
    moment the field is merely declared, before any real leaking data is
    even wired up. Revert immediately after observing the failure; this
    class intentionally has no test bodies of its own.
    """
