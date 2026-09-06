"""API-level tests for Person CRUD, validation wiring, bulk create and the
revision/restore endpoints. Unit coverage for each rule itself lives in
`test_person_rules.py` (no DB); this file checks the view wires those rules
up correctly, plus the permission matrix and soft-delete behaviour.
"""

import datetime as dt
import json

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.models import Person, PersonRevision
from giapha.tests.factories import build_clan_fixture, build_person


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def persons_url(clan_id):
    return reverse('person-list-create', kwargs={'clan_id': clan_id})


def person_url(clan_id, person_id):
    return reverse('person-detail', kwargs={'clan_id': clan_id, 'person_id': person_id})


def revisions_url(clan_id, person_id):
    return reverse('person-revisions', kwargs={'clan_id': clan_id, 'person_id': person_id})


def restore_url(clan_id, person_id, revision_id):
    return reverse(
        'person-restore', kwargs={'clan_id': clan_id, 'person_id': person_id, 'revision_id': revision_id},
    )


MINIMAL_PERSON = {'ho_ten': 'Nguyễn Văn A', 'gioi_tinh': 'nam'}


class PersonPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']
        cls.other_fixture = build_clan_fixture(ten_ho='Trần tộc', suffix='_other')

    def test_viewer_gets_403_on_create(self):
        response = client_for(self.fixture['viewer']).post(
            persons_url(self.clan.id), MINIMAL_PERSON, format='json',
        )
        self.assertEqual(403, response.status_code)

    def test_editor_of_a_different_clan_gets_404(self):
        outsider_editor = self.other_fixture['editor']
        response = client_for(outsider_editor).post(
            persons_url(self.clan.id), MINIMAL_PERSON, format='json',
        )
        self.assertEqual(404, response.status_code)

    def test_editor_can_create(self):
        response = client_for(self.fixture['editor']).post(
            persons_url(self.clan.id), MINIMAL_PERSON, format='json',
        )
        self.assertEqual(201, response.status_code)

    def test_any_member_can_list(self):
        for role in ('owner', 'editor', 'viewer'):
            with self.subTest(role=role):
                response = client_for(self.fixture[role]).get(persons_url(self.clan.id))
                self.assertEqual(200, response.status_code)


class PersonCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']

    def test_create_returns_embedded_parent_name(self):
        father = build_person(self.clan, ho_ten='Ông Nội')
        response = client_for(self.fixture['editor']).post(
            persons_url(self.clan.id),
            dict(MINIMAL_PERSON, father_id=father.id),
            format='json',
        )
        self.assertEqual(201, response.status_code)
        data = response.json()['data']
        self.assertEqual(father.id, data['father_id'])
        self.assertEqual('Ông Nội', data['father_name'])

    def test_create_records_a_revision(self):
        response = client_for(self.fixture['editor']).post(
            persons_url(self.clan.id), MINIMAL_PERSON, format='json',
        )
        person_id = response.json()['data']['id']
        self.assertEqual(1, PersonRevision.objects.filter(person_id=person_id, action='create').count())

    def test_patch_updates_field_and_records_revision(self):
        person = build_person(self.clan, ho_ten='Trước sửa')
        response = client_for(self.fixture['editor']).patch(
            person_url(self.clan.id, person.id), {'ho_ten': 'Sau sửa'}, format='json',
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual('Sau sửa', response.json()['data']['ho_ten'])
        self.assertEqual(1, PersonRevision.objects.filter(person=person, action='update').count())

    def test_delete_without_children_soft_deletes(self):
        person = build_person(self.clan)
        response = client_for(self.fixture['editor']).delete(person_url(self.clan.id, person.id))
        self.assertEqual(204, response.status_code)
        person.refresh_from_db()
        self.assertTrue(person.is_deleted)

    def test_delete_with_children_is_blocked_and_names_the_count(self):
        parent = build_person(self.clan, ho_ten='Cha')
        build_person(self.clan, ho_ten='Con 1', father=parent)
        build_person(self.clan, ho_ten='Con 2', father=parent)

        response = client_for(self.fixture['editor']).delete(person_url(self.clan.id, parent.id))
        self.assertEqual(400, response.status_code)
        self.assertIn('2', response.json()['detail'])
        parent.refresh_from_db()
        self.assertFalse(parent.is_deleted)

    def test_soft_deleted_person_disappears_from_list_and_detail(self):
        person = build_person(self.clan)
        person.is_deleted = True
        person.save(update_fields=['is_deleted'])

        client = client_for(self.fixture['owner'])
        self.assertEqual(404, client.get(person_url(self.clan.id, person.id)).status_code)
        ids = [row['id'] for row in client.get(persons_url(self.clan.id)).json()['data']]
        self.assertNotIn(person.id, ids)

    def test_list_is_paginated(self):
        for i in range(3):
            build_person(self.clan, ho_ten='Người {}'.format(i))
        response = client_for(self.fixture['owner']).get(persons_url(self.clan.id))
        body = response.json()
        self.assertIn('count', body)
        self.assertIn('next', body)
        self.assertGreaterEqual(body['count'], 3)


class PersonValidationApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']
        cls.other_fixture = build_clan_fixture(ten_ho='Trần tộc', suffix='_val')

    def test_father_from_another_clan_is_rejected(self):
        foreign_father = build_person(self.other_fixture['clan'], ho_ten='Người họ khác')
        response = client_for(self.fixture['editor']).post(
            persons_url(self.clan.id), dict(MINIMAL_PERSON, father_id=foreign_father.id), format='json',
        )
        self.assertEqual(400, response.status_code)

    def test_updating_into_a_cycle_is_rejected(self):
        grandparent = build_person(self.clan, ho_ten='Đời 1')
        parent = build_person(self.clan, ho_ten='Đời 2', father=grandparent)
        child = build_person(self.clan, ho_ten='Đời 3', father=parent)

        # Assigning the grandchild as the grandparent's father closes the loop.
        response = client_for(self.fixture['editor']).patch(
            person_url(self.clan.id, grandparent.id), {'father_id': child.id}, format='json',
        )
        self.assertEqual(400, response.status_code)

    def test_self_as_parent_is_rejected(self):
        person = build_person(self.clan)
        response = client_for(self.fixture['editor']).patch(
            person_url(self.clan.id, person.id), {'father_id': person.id}, format='json',
        )
        self.assertEqual(400, response.status_code)

    def test_death_before_birth_is_rejected(self):
        response = client_for(self.fixture['editor']).post(
            persons_url(self.clan.id),
            dict(MINIMAL_PERSON, birth_solar='2000-01-01', death_solar='1999-01-01'),
            format='json',
        )
        self.assertEqual(400, response.status_code)

    def test_parent_born_less_than_12_years_before_child_is_rejected(self):
        father = build_person(self.clan, ho_ten='Cha trẻ', birth_solar=dt.date(1990, 1, 1))
        response = client_for(self.fixture['editor']).post(
            persons_url(self.clan.id),
            dict(MINIMAL_PERSON, father_id=father.id, birth_solar='1998-01-01'),
            format='json',
        )
        self.assertEqual(400, response.status_code)

    def test_force_true_bypasses_the_age_gap_check_for_owner(self):
        father = build_person(self.clan, ho_ten='Cha trẻ', birth_solar=dt.date(1990, 1, 1))
        response = client_for(self.fixture['owner']).post(
            persons_url(self.clan.id) + '?force=true',
            dict(MINIMAL_PERSON, father_id=father.id, birth_solar='1998-01-01'),
            format='json',
        )
        self.assertEqual(201, response.status_code)

    def test_editor_cannot_use_force(self):
        father = build_person(self.clan, ho_ten='Cha trẻ', birth_solar=dt.date(1990, 1, 1))
        response = client_for(self.fixture['editor']).post(
            persons_url(self.clan.id) + '?force=true',
            dict(MINIMAL_PERSON, father_id=father.id, birth_solar='1998-01-01'),
            format='json',
        )
        self.assertEqual(403, response.status_code)

    @override_settings(MAX_CLAN_PERSONS=2)
    def test_clan_size_cap_is_enforced(self):
        build_person(self.clan)
        build_person(self.clan)
        response = client_for(self.fixture['editor']).post(
            persons_url(self.clan.id), MINIMAL_PERSON, format='json',
        )
        self.assertEqual(400, response.status_code)


class PersonBulkCreateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']

    def test_bulk_create_of_200_succeeds_in_one_request(self):
        items = [{'ho_ten': 'Người {}'.format(i), 'gioi_tinh': 'nam'} for i in range(200)]
        response = client_for(self.fixture['editor']).post(persons_url(self.clan.id), items, format='json')
        self.assertEqual(201, response.status_code)
        self.assertEqual(200, len(response.json()['data']))
        self.assertEqual(200, Person.objects.filter(clan=self.clan, is_deleted=False).count())

    def test_bulk_create_over_200_is_rejected(self):
        items = [{'ho_ten': 'Người {}'.format(i), 'gioi_tinh': 'nam'} for i in range(201)]
        response = client_for(self.fixture['editor']).post(persons_url(self.clan.id), items, format='json')
        self.assertEqual(400, response.status_code)
        self.assertEqual(0, Person.objects.filter(clan=self.clan).count())

    def test_batch_read_overhead_does_not_scale_with_batch_size(self):
        """`clan_edges`/`birth_solar_by_id`/`active_person_count` are each
        loaded ONCE per request and updated in memory afterwards, so the
        fixed read overhead for a 40-row batch must equal that of a 4-row
        batch -- only the per-record insert/revision writes should scale.
        Isolated in fresh clans so query counts aren't skewed by fixture data.

        H2 regression: every row below carries `father_id` -- the exact shape
        that triggered the N+1 (`PersonReadSerializer.get_father_name` doing
        one SELECT per row with a parent set, on freshly-created instances
        whose `father` relation cache is empty). The original version of
        this test used parent-less rows, the one case where the bug cannot
        fire, and passed despite the bug. If the N+1 (or the `generation`
        bulk_update/re-fetch this fix added) ever regressed into scaling with
        N, the delta below would stop being exactly `2 * (large - small)`.
        """
        small_fixture = build_clan_fixture(ten_ho='Batch nhỏ', suffix='_batch_small')
        large_fixture = build_clan_fixture(ten_ho='Batch lớn', suffix='_batch_large')
        small_father = build_person(small_fixture['clan'], ho_ten='Cha nhỏ')
        large_father = build_person(large_fixture['clan'], ho_ten='Cha lớn')

        small_items = [
            {'ho_ten': 'Người {}'.format(i), 'gioi_tinh': 'nam', 'father_id': small_father.id}
            for i in range(4)
        ]
        large_items = [
            {'ho_ten': 'Người {}'.format(i), 'gioi_tinh': 'nam', 'father_id': large_father.id}
            for i in range(40)
        ]

        small_queries = self._count_queries(small_fixture, small_items)
        large_queries = self._count_queries(large_fixture, large_items)

        # Each record costs exactly 2 writes (Person insert + PersonRevision
        # insert); the difference between batches must equal exactly that,
        # proving neither the edges/birth_map/count reads nor the father-name
        # lookup repeat per record. This is the real ceiling: per-record cost
        # is fixed at 2 regardless of whether the row has a parent.
        self.assertEqual(2 * (len(large_items) - len(small_items)), large_queries - small_queries)

    @staticmethod
    def _count_queries(fixture, items):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as capture:
            client_for(fixture['editor']).post(persons_url(fixture['clan'].id), items, format='json')
        return len(capture.captured_queries)

    def test_one_invalid_row_rolls_back_the_whole_batch(self):
        items = [
            {'ho_ten': 'Hợp lệ', 'gioi_tinh': 'nam'},
            {'ho_ten': 'Không hợp lệ', 'gioi_tinh': 'nam', 'father_id': 999999},
        ]
        response = client_for(self.fixture['editor']).post(persons_url(self.clan.id), items, format='json')
        self.assertEqual(400, response.status_code)
        self.assertEqual(0, Person.objects.filter(clan=self.clan).count())


class PersonRevisionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']

    def test_restore_returns_exactly_the_prior_field_values(self):
        person = build_person(self.clan, ho_ten='Tên gốc', que_quan='Quê gốc')
        editor_client = client_for(self.fixture['editor'])

        patch_response = editor_client.patch(
            person_url(self.clan.id, person.id),
            {'ho_ten': 'Tên đã sửa', 'que_quan': 'Quê đã sửa'},
            format='json',
        )
        self.assertEqual(200, patch_response.status_code)

        revisions = editor_client.get(revisions_url(self.clan.id, person.id)).json()['data']
        pre_update_revision_id = revisions[0]['id']  # newest-first; this is the pre-patch snapshot

        restore_response = editor_client.post(restore_url(self.clan.id, person.id, pre_update_revision_id))
        self.assertEqual(200, restore_response.status_code)
        data = restore_response.json()['data']
        self.assertEqual('Tên gốc', data['ho_ten'])
        self.assertEqual('Quê gốc', data['que_quan'])

    def test_revisions_survive_soft_delete(self):
        person = build_person(self.clan)
        editor_client = client_for(self.fixture['editor'])
        editor_client.delete(person_url(self.clan.id, person.id))

        response = editor_client.get(revisions_url(self.clan.id, person.id))
        self.assertEqual(200, response.status_code)
        actions = [row['action'] for row in response.json()['data']]
        self.assertIn('delete', actions)

    def test_viewer_cannot_see_revisions(self):
        person = build_person(self.clan)
        response = client_for(self.fixture['viewer']).get(revisions_url(self.clan.id, person.id))
        self.assertEqual(403, response.status_code)

    def test_restoring_unknown_revision_is_404(self):
        person = build_person(self.clan)
        response = client_for(self.fixture['editor']).post(restore_url(self.clan.id, person.id, 999999))
        self.assertEqual(404, response.status_code)

    def test_restore_never_undeletes(self):
        """Product decision 4: restoring genealogical content must never be
        an implicit undelete. `is_deleted` is now excluded from the
        snapshot entirely (`services.revision._EXCLUDED_FIELDS`), so it
        cannot come back via `restore()`'s blind `setattr` loop.
        """
        person = build_person(self.clan, ho_ten='Ai đó', que_quan='Quê cũ')
        editor_client = client_for(self.fixture['editor'])

        editor_client.patch(person_url(self.clan.id, person.id), {'que_quan': 'Quê mới'}, format='json')
        pre_delete_revision_id = editor_client.get(
            revisions_url(self.clan.id, person.id)
        ).json()['data'][0]['id']

        editor_client.delete(person_url(self.clan.id, person.id))
        person.refresh_from_db()
        self.assertTrue(person.is_deleted)

        response = editor_client.post(restore_url(self.clan.id, person.id, pre_delete_revision_id))
        self.assertEqual(200, response.status_code)
        person.refresh_from_db()
        self.assertTrue(person.is_deleted, 'restore must not silently resurrect a soft-deleted person')
        self.assertEqual('Quê cũ', person.que_quan, 'non-deletion content must still restore correctly')

    def test_restore_does_not_reattach_a_foreign_photo_key(self):
        """C1 (critical), end-to-end through the actual restore endpoint:
        `photo_key` is now excluded from BOTH `snapshot()` and `restore()`
        (`services.revision._EXCLUDED_FIELDS`; see `test_revision_service.py`
        for the direct unit coverage of that filter). This revision's
        payload is hand-built (`PersonRevision.objects.create` directly,
        bypassing `record()`/`snapshot()`) with a `photo_key` belonging to
        another clan/person entirely, simulating a revision recorded before
        this fix existed -- proving the endpoint itself, not just the pure
        function, never re-attaches it.
        """
        person = build_person(self.clan, ho_ten='Chưa từng có ảnh')
        foreign_payload = json.dumps({'photo_key': 'giapha/999/999/stolen.jpg'})
        revision = PersonRevision.objects.create(
            person=person, actor=self.fixture['editor'], action='update', payload_json=foreign_payload,
        )

        response = client_for(self.fixture['editor']).post(
            restore_url(self.clan.id, person.id, revision.id)
        )
        self.assertEqual(200, response.status_code)
        person.refresh_from_db()
        self.assertEqual('', person.photo_key)

    def test_restore_reruns_cycle_validation_against_the_current_tree(self):
        """H3, reproducing the reviewer's exact end-to-end sequence:
        A is father of B; a revision of B is recorded; B's father is cleared
        and A's father is set to B (legal at that point); restoring B's old
        revision would re-close the cycle A<->B. The write path forbids this
        for a normal PATCH, so restore must forbid it too.
        """
        editor_client = client_for(self.fixture['editor'])
        a = build_person(self.clan, ho_ten='A')
        b = build_person(self.clan, ho_ten='B', father=a)

        editor_client.patch(person_url(self.clan.id, b.id), {'ho_ten': 'B đã sửa'}, format='json')
        pre_change_revision_id = editor_client.get(
            revisions_url(self.clan.id, b.id)
        ).json()['data'][0]['id']

        editor_client.patch(person_url(self.clan.id, b.id), {'father_id': None}, format='json')
        set_a_father = editor_client.patch(
            person_url(self.clan.id, a.id), {'father_id': b.id}, format='json',
        )
        self.assertEqual(200, set_a_father.status_code)

        response = editor_client.post(restore_url(self.clan.id, b.id, pre_change_revision_id))
        self.assertEqual(400, response.status_code)

        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(b.id, a.father_id)
        self.assertIsNone(b.father_id, 'the rejected restore must not have partially applied')

    def test_restore_is_paginated_and_uses_select_related_for_actor(self):
        """H6: the revisions list must not do 1 query per revision for
        `actor_username`, and must be paginated like the other list
        endpoints.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        person = build_person(self.clan, ho_ten='Nhiều lịch sử')
        editor_client = client_for(self.fixture['editor'])
        for i in range(12):
            editor_client.patch(person_url(self.clan.id, person.id), {'que_quan': 'Q{}'.format(i)}, format='json')

        with CaptureQueriesContext(connection) as capture:
            response = editor_client.get(revisions_url(self.clan.id, person.id))
        self.assertEqual(200, response.status_code)
        self.assertLessEqual(
            len(capture.captured_queries), 6,
            '12 revisions must not cost ~1 query per revision (N+1 on actor_username)',
        )
        body = response.json()
        self.assertIn('count', body)
        self.assertIn('next', body)
        self.assertGreaterEqual(body['count'], 12)


class PersonGenerationOnCreateTests(TestCase):
    """H1: `generation` must be computed on create (single AND bulk), not
    only on a PATCH that changes a parent, and must never be client-settable.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_gen')
        cls.clan = cls.fixture['clan']

    def test_root_person_created_via_api_gets_generation_one(self):
        response = client_for(self.fixture['editor']).post(
            persons_url(self.clan.id), MINIMAL_PERSON, format='json',
        )
        self.assertEqual(201, response.status_code)
        self.assertEqual(1, response.json()['data']['generation'])

    def test_child_of_an_existing_person_gets_parent_generation_plus_one(self):
        root = build_person(self.clan, ho_ten='Gốc')
        root.generation = 1
        root.save(update_fields=['generation'])

        response = client_for(self.fixture['editor']).post(
            persons_url(self.clan.id), dict(MINIMAL_PERSON, father_id=root.id), format='json',
        )
        self.assertEqual(201, response.status_code)
        self.assertEqual(2, response.json()['data']['generation'])

    def test_bulk_create_computes_generation_for_every_row(self):
        root = build_person(self.clan, ho_ten='Gốc hàng loạt')
        root.generation = 1
        root.save(update_fields=['generation'])

        items = [
            {'ho_ten': 'Con {}'.format(i), 'gioi_tinh': 'nam', 'father_id': root.id}
            for i in range(5)
        ]
        response = client_for(self.fixture['editor']).post(persons_url(self.clan.id), items, format='json')
        self.assertEqual(201, response.status_code)
        generations = [row['generation'] for row in response.json()['data']]
        self.assertEqual([2] * 5, generations)

    def test_client_supplied_generation_is_ignored(self):
        response = client_for(self.fixture['editor']).post(
            persons_url(self.clan.id), dict(MINIMAL_PERSON, generation=999), format='json',
        )
        self.assertEqual(201, response.status_code)
        self.assertEqual(1, response.json()['data']['generation'], 'a client must never set generation directly')
        self.assertEqual(1, Person.objects.get(id=response.json()['data']['id']).generation)


class PersonDeathYearBoundTests(TestCase):
    """H5a: `?death_year=` must be bounded before it reaches Django's
    `YearLookup`, which raises a stdlib `OverflowError` (-> uncaught 500) on
    an out-of-range year.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_deathyear')
        cls.clan = cls.fixture['clan']

    def test_overflowing_death_year_is_a_400_not_a_500(self):
        response = client_for(self.fixture['owner']).get(
            persons_url(self.clan.id) + '?death_year=999999999999',
        )
        self.assertEqual(400, response.status_code)

    def test_negative_death_year_is_a_400(self):
        response = client_for(self.fixture['owner']).get(persons_url(self.clan.id) + '?death_year=-5')
        self.assertEqual(400, response.status_code)

    def test_in_range_death_year_still_filters(self):
        build_person(self.clan, ho_ten='Đã mất', death_solar=dt.date(1999, 5, 1))
        response = client_for(self.fixture['owner']).get(persons_url(self.clan.id) + '?death_year=1999')
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, response.json()['count'])


class PersonDeleteDanglingPointerTests(TestCase):
    """H4: a soft-deleted child still carries `father_id`/`mother_id` -- the
    delete guard must account for it, not just for live children.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_dangle')
        cls.clan = cls.fixture['clan']

    def test_delete_blocked_while_a_soft_deleted_child_still_points_at_it(self):
        parent = build_person(self.clan, ho_ten='Cha')
        child = build_person(self.clan, ho_ten='Con', father=parent)
        child.is_deleted = True
        child.save(update_fields=['is_deleted'])

        response = client_for(self.fixture['editor']).delete(person_url(self.clan.id, parent.id))
        self.assertEqual(400, response.status_code)
        parent.refresh_from_db()
        self.assertFalse(parent.is_deleted)


class PersonHeadAndOptionsPermissionTests(TestCase):
    """M1: `HEAD`/`OPTIONS` must use the same permission as `GET`, not the
    stricter write permission -- they were previously matched by `!= 'GET'`.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_headopts')
        cls.clan = cls.fixture['clan']

    def test_viewer_head_and_options_on_person_list_are_not_403(self):
        viewer_client = client_for(self.fixture['viewer'])
        self.assertEqual(200, viewer_client.head(persons_url(self.clan.id)).status_code)
        self.assertEqual(200, viewer_client.options(persons_url(self.clan.id)).status_code)

    def test_viewer_head_and_options_on_person_detail_are_not_403(self):
        person = build_person(self.clan)
        viewer_client = client_for(self.fixture['viewer'])
        self.assertEqual(200, viewer_client.head(person_url(self.clan.id, person.id)).status_code)
        self.assertEqual(200, viewer_client.options(person_url(self.clan.id, person.id)).status_code)
