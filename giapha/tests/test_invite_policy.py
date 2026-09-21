"""`services.invite_policy.invite_initial_status` -- full decision table."""

from django.test import SimpleTestCase

from giapha.services.invite_policy import STATUS_ACTIVE, STATUS_PENDING, invite_initial_status

IN_SCOPE = {10, 11}
A = STATUS_ACTIVE
P = STATUS_PENDING

# (caller_role, invite_role, person_id, writable_ids, expected)
TABLE = [
    ('owner', 'viewer', None, None, A),
    ('owner', 'editor', None, None, A),
    ('owner', 'viewer', 99, None, A),
    ('manager', 'viewer', None, None, A),
    ('manager', 'viewer', 99, None, A),
    ('manager', 'editor', None, None, P),
    ('manager', 'editor', 10, None, P),
    ('editor', 'viewer', 10, None, A),
    ('editor', 'viewer', None, None, P),
    ('editor', 'editor', 10, None, P),
    ('viewer', 'viewer', 10, IN_SCOPE, A),
    ('viewer', 'viewer', 99, IN_SCOPE, P),
    ('viewer', 'viewer', None, IN_SCOPE, P),
    ('viewer', 'editor', 10, IN_SCOPE, P),
    ('viewer', 'viewer', 10, set(), P),
]


class InvitePolicyTests(SimpleTestCase):
    def test_decision_table(self):
        for caller_role, invite_role, person_id, writable, expected in TABLE:
            with self.subTest(caller=caller_role, invite=invite_role, person=person_id, writable=writable):
                self.assertEqual(expected, invite_initial_status(caller_role, invite_role, person_id, writable))
