"""Unit tests for `giapha.services.revision` -- pure `snapshot()`/`restore()`,
no ORM writes. Every `Person` instance here is constructed in memory and
never `.save()`d, so this suite runs on `SimpleTestCase` (same reasoning as
`test_person_rules.py`: services/ stays importable and testable without a
database, see docs/code-standards.md -> Layering).
"""

import json

from django.test import SimpleTestCase

from giapha.models import Person
from giapha.services.revision import _EXCLUDED_FIELDS, restore, snapshot


class RestorePhotoKeyExclusionTests(SimpleTestCase):
    """C1 (critical): a revision's write-side exclusion of `photo_key` from
    `snapshot()` only protects payloads recorded AFTER the fix -- every
    payload already sitting in the database from before it was excluded
    still carries a `photo_key` key, since `payload_json` is never rewritten
    once a revision is recorded. `restore()` must therefore filter
    `_EXCLUDED_FIELDS` on READ too, or `_EXCLUDED_FIELDS` only ever protects
    the future, never the past.
    """

    def test_restore_ignores_a_hand_built_payload_carrying_photo_key(self):
        """This is the test that actually proves the read-side filter
        works. The payload below is built BY HAND (bypassing `record()`/
        `snapshot()`, which can no longer produce a `photo_key` key at all
        post-fix) specifically to simulate a pre-fix revision row still
        sitting in the database. Excluding `photo_key` from `snapshot()`
        alone would do nothing to protect against this payload -- only
        filtering inside `restore()` itself does.
        """
        person = Person(photo_key='giapha/1/1/original.jpg')
        payload = json.dumps({'photo_key': 'giapha/9/9/stolen.jpg'})

        restore(person, payload)

        self.assertEqual(
            'giapha/1/1/original.jpg', person.photo_key,
            'a photo_key present in a stored payload must never be re-applied by restore()',
        )

    def test_restore_still_restores_a_normal_genealogical_field(self):
        """Guard against over-filtering: only `_EXCLUDED_FIELDS` should be
        skipped -- every other field in the payload must still come back.
        """
        person = Person(ho_ten='Tên hiện tại', que_quan='Quê hiện tại')
        payload = json.dumps({
            'ho_ten': 'Tên gốc', 'que_quan': 'Quê gốc', 'photo_key': 'giapha/9/9/stolen.jpg',
        })

        restore(person, payload)

        self.assertEqual('Tên gốc', person.ho_ten)
        self.assertEqual('Quê gốc', person.que_quan)


class SnapshotPhotoKeyExclusionTests(SimpleTestCase):
    def test_snapshot_never_includes_photo_key(self):
        """Write-side half of the fix: a snapshot taken from now on never
        contains `photo_key`, so a normal (non-hand-built) restore has
        nothing to leak in the first place.
        """
        person = Person(clan_id=1, ho_ten='X', gioi_tinh='nam', photo_key='giapha/1/1/current.jpg')
        data = json.loads(snapshot(person))
        self.assertNotIn('photo_key', data)

    def test_photo_key_is_in_excluded_fields(self):
        self.assertIn('photo_key', _EXCLUDED_FIELDS)
