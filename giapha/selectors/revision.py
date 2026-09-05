"""Write helper for PersonRevision rows.

`snapshot()`/`restore()` are pure and live in `services/revision.py`; the one
function here touches the ORM, which is why it sits in `selectors/` instead --
`services/` stays importable without a database so `test_person_rules.py` can
run on `SimpleTestCase` (see docs/code-standards.md).
"""

from giapha.models import PersonRevision
from giapha.services.revision import snapshot


def record(person, actor, action):
    """Snapshot `person`'s CURRENT (pre-change) state and store it. Call this
    before mutating/saving `person`, not after.
    """
    return PersonRevision.objects.create(
        person=person, actor=actor, action=action, payload_json=snapshot(person),
    )


def revisions_of(person):
    """Every revision of `person`, newest first, with `actor` preloaded --
    `PersonRevisionSerializer.actor_username` walks `actor.username`, so a
    caller handing this queryset an unprefetched one is an N+1.
    """
    return PersonRevision.objects.filter(person=person).select_related('actor').order_by('-created_at')


def revision_for_person(person, revision_id):
    return PersonRevision.objects.filter(id=revision_id, person=person).first()
