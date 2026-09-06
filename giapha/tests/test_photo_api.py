"""API-level tests for the presigned S3/R2 photo endpoints (phase 8).

`boto3` is mocked completely -- see `setUp()` in every class below, which
patches `giapha.services.storage.boto3.client` and calls
`storage.reset_client_cache()` so each test gets its own fresh `Mock`
regardless of the config tuple staying the same across tests in a class.
NOTHING here touches the network; the real end-to-end path (a genuine
bucket) is documented as unverified in `docs/deployment-guide.md`.
"""

import uuid
from unittest import mock

from botocore.exceptions import ClientError
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.services import storage
from giapha.tests.factories import build_clan_fixture, build_person

S3_TEST_SETTINGS = dict(
    S3_ENDPOINT_URL='', S3_BUCKET='test-bucket', S3_ACCESS_KEY_ID='test-key',
    S3_SECRET_ACCESS_KEY='test-secret', S3_REGION='auto',
)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def upload_url_endpoint(clan_id, person_id):
    return reverse('person-photo-upload-url', kwargs={'clan_id': clan_id, 'person_id': person_id})


def photo_endpoint(clan_id, person_id):
    return reverse('person-photo', kwargs={'clan_id': clan_id, 'person_id': person_id})


def photo_urls_endpoint(clan_id):
    return reverse('clan-photo-urls', kwargs={'clan_id': clan_id})


def person_endpoint(clan_id, person_id):
    return reverse('person-detail', kwargs={'clan_id': clan_id, 'person_id': person_id})


def person_list_endpoint(clan_id):
    return reverse('person-list-create', kwargs={'clan_id': clan_id})


class MockedBotoMixin:
    """Patches `boto3.client` with a fresh `Mock` per test and resets the
    module-level client cache in `services.storage` so that mock is actually
    what gets used -- without the reset, the cache built by an earlier test
    (same config tuple under `@override_settings`) would be served instead.
    """

    def setUp(self):
        super().setUp()
        storage.reset_client_cache()
        patcher = mock.patch('giapha.services.storage.boto3.client')
        self.mock_boto_client_factory = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_client = mock.Mock()
        self.mock_boto_client_factory.return_value = self.mock_client
        self.mock_client.generate_presigned_url.return_value = 'https://test-bucket.example/signed'
        self.mock_client.head_object.return_value = {
            'ContentLength': 1000, 'ContentType': 'image/jpeg',
        }


@override_settings(**S3_TEST_SETTINGS)
class PhotoUploadUrlTests(MockedBotoMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_photo_upload')
        cls.clan = cls.fixture['clan']
        cls.person = build_person(cls.clan, ho_ten='Ảnh')

    def test_editor_gets_presigned_upload_url_with_clan_and_person_prefixed_key(self):
        response = client_for(self.fixture['editor']).post(
            upload_url_endpoint(self.clan.id, self.person.id),
            {'content_type': 'image/jpeg', 'size': 1000}, format='json',
        )
        self.assertEqual(200, response.status_code)
        data = response.json()['data']
        self.assertEqual('https://test-bucket.example/signed', data['upload_url'])
        self.assertTrue(data['key'].startswith('giapha/{}/{}/'.format(self.clan.id, self.person.id)))
        self.assertEqual(300, data['expires_in'])

    def test_bad_content_type_is_rejected(self):
        response = client_for(self.fixture['editor']).post(
            upload_url_endpoint(self.clan.id, self.person.id),
            {'content_type': 'application/pdf', 'size': 1000}, format='json',
        )
        self.assertEqual(400, response.status_code)

    def test_oversized_declared_size_is_rejected(self):
        response = client_for(self.fixture['editor']).post(
            upload_url_endpoint(self.clan.id, self.person.id),
            {'content_type': 'image/jpeg', 'size': 6 * 1024 * 1024}, format='json',
        )
        self.assertEqual(400, response.status_code)

    def test_viewer_gets_403(self):
        response = client_for(self.fixture['viewer']).post(
            upload_url_endpoint(self.clan.id, self.person.id),
            {'content_type': 'image/jpeg', 'size': 1000}, format='json',
        )
        self.assertEqual(403, response.status_code)

    def test_outsider_gets_404(self):
        response = client_for(self.fixture['outsider']).post(
            upload_url_endpoint(self.clan.id, self.person.id),
            {'content_type': 'image/jpeg', 'size': 1000}, format='json',
        )
        self.assertEqual(404, response.status_code)


class StorageUnconfiguredTests(MockedBotoMixin, TestCase):
    """Deliberately NO `@override_settings` here -- the test settings leave
    every `S3_*` variable empty, which is the state every other giapha test
    already runs under. This class proves that state is safe.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_photo_unconfigured')
        cls.clan = cls.fixture['clan']
        cls.person = build_person(cls.clan, ho_ten='Chưa cấu hình')

    def test_upload_url_endpoint_is_503(self):
        response = client_for(self.fixture['editor']).post(
            upload_url_endpoint(self.clan.id, self.person.id),
            {'content_type': 'image/jpeg', 'size': 1000}, format='json',
        )
        self.assertEqual(503, response.status_code)

    def test_confirm_endpoint_is_503(self):
        response = client_for(self.fixture['editor']).post(
            photo_endpoint(self.clan.id, self.person.id), {'key': 'giapha/x/1/a.jpg'}, format='json',
        )
        self.assertEqual(503, response.status_code)

    def test_delete_endpoint_is_503(self):
        response = client_for(self.fixture['editor']).delete(photo_endpoint(self.clan.id, self.person.id))
        self.assertEqual(503, response.status_code)

    def test_photo_urls_endpoint_is_503(self):
        response = client_for(self.fixture['viewer']).post(
            photo_urls_endpoint(self.clan.id), {'person_ids': [self.person.id]}, format='json',
        )
        self.assertEqual(503, response.status_code)

    def test_rest_of_api_keeps_working(self):
        response = client_for(self.fixture['editor']).get(person_endpoint(self.clan.id, self.person.id))
        self.assertEqual(200, response.status_code)
        self.assertIsNone(response.json()['data']['photo_url'])


@override_settings(**S3_TEST_SETTINGS)
class ConfirmPhotoTests(MockedBotoMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_photo_confirm')
        cls.clan = cls.fixture['clan']
        cls.person = build_person(cls.clan, ho_ten='Người xác nhận ảnh')
        cls.other_person_same_clan = build_person(cls.clan, ho_ten='Người khác cùng họ')
        cls.other_fixture = build_clan_fixture(ten_ho='Trần tộc', suffix='_photo_confirm_other')

    def _key_for(self, person):
        return 'giapha/{}/{}/{}.jpg'.format(self.clan.id, person.id, uuid.uuid4().hex)

    def test_confirm_writes_photo_key_and_returns_presigned_photo_url(self):
        key = self._key_for(self.person)
        response = client_for(self.fixture['editor']).post(
            photo_endpoint(self.clan.id, self.person.id), {'key': key}, format='json',
        )
        self.assertEqual(200, response.status_code)
        self.person.refresh_from_db()
        self.assertEqual(key, self.person.photo_key)
        self.assertEqual('https://test-bucket.example/signed', response.json()['data']['photo_url'])

    def test_key_belonging_to_another_clan_is_rejected(self):
        key = 'giapha/{}/{}/{}.jpg'.format(
            self.other_fixture['clan'].id, self.person.id, uuid.uuid4().hex,
        )
        response = client_for(self.fixture['editor']).post(
            photo_endpoint(self.clan.id, self.person.id), {'key': key}, format='json',
        )
        self.assertEqual(400, response.status_code)
        self.person.refresh_from_db()
        self.assertEqual('', self.person.photo_key)

    def test_key_belonging_to_another_person_in_same_clan_is_rejected(self):
        key = self._key_for(self.other_person_same_clan)
        response = client_for(self.fixture['editor']).post(
            photo_endpoint(self.clan.id, self.person.id), {'key': key}, format='json',
        )
        self.assertEqual(400, response.status_code)

    def test_path_traversal_key_is_rejected(self):
        """H1: a key like `giapha/{c}/{p}/../../{other}/{other}/x.jpg`
        passes a plain `.startswith()` prefix check (which is exactly what
        the old implementation did) since it still starts with the right
        prefix -- but it does not match `_KEY_RE`'s exact minted shape, so
        the fixed confirm view must reject it.
        """
        traversal_key = 'giapha/{}/{}/../../{}/{}/stolen.jpg'.format(
            self.clan.id, self.person.id,
            self.other_fixture['clan'].id, self.person.id,
        )
        response = client_for(self.fixture['editor']).post(
            photo_endpoint(self.clan.id, self.person.id), {'key': traversal_key}, format='json',
        )
        self.assertEqual(400, response.status_code)
        self.person.refresh_from_db()
        self.assertEqual('', self.person.photo_key)
        self.mock_client.head_object.assert_not_called()

    def test_bare_directory_key_is_rejected(self):
        """H1: `giapha/{c}/{p}/` (no filename at all) also starts with the
        prefix but isn't a shape this server ever mints.
        """
        bare_key = 'giapha/{}/{}/'.format(self.clan.id, self.person.id)
        response = client_for(self.fixture['editor']).post(
            photo_endpoint(self.clan.id, self.person.id), {'key': bare_key}, format='json',
        )
        self.assertEqual(400, response.status_code)

    def test_head_reporting_object_over_5mb_is_rejected(self):
        self.mock_client.head_object.return_value = {
            'ContentLength': 6 * 1024 * 1024, 'ContentType': 'image/jpeg',
        }
        key = self._key_for(self.person)
        response = client_for(self.fixture['editor']).post(
            photo_endpoint(self.clan.id, self.person.id), {'key': key}, format='json',
        )
        self.assertEqual(400, response.status_code)
        self.person.refresh_from_db()
        self.assertEqual('', self.person.photo_key)

    def test_head_reporting_disallowed_content_type_is_rejected(self):
        self.mock_client.head_object.return_value = {
            'ContentLength': 1000, 'ContentType': 'application/pdf',
        }
        key = self._key_for(self.person)
        response = client_for(self.fixture['editor']).post(
            photo_endpoint(self.clan.id, self.person.id), {'key': key}, format='json',
        )
        self.assertEqual(400, response.status_code)

    def test_head_object_not_found_client_error_is_rejected(self):
        """H2: the `if meta is None: raise BadRequestException(...)` guard
        in `views/photo.py` was proven mutation-blind -- every other test in
        this class hardwires `head_object` to succeed, so deleting that
        guard entirely still left the suite green. This test drives
        `head_object` into actually raising the `ClientError` that
        `storage.head()` maps to `None`, so the guard has real coverage.
        """
        self.mock_client.head_object.side_effect = ClientError(
            {'Error': {'Code': '404'}}, 'HeadObject',
        )
        key = self._key_for(self.person)
        response = client_for(self.fixture['editor']).post(
            photo_endpoint(self.clan.id, self.person.id), {'key': key}, format='json',
        )
        self.assertEqual(400, response.status_code)
        self.person.refresh_from_db()
        self.assertEqual('', self.person.photo_key)

    def test_delete_object_failure_on_replace_still_persists_the_new_key(self):
        """Covers `_swallow_delete`: a failed delete of the OLD object on a
        photo replace must not turn a successful confirm into an error
        response, and the NEW key must be what actually gets persisted.
        """
        old_key = self._key_for(self.person)
        self.person.photo_key = old_key
        self.person.save(update_fields=['photo_key'])
        self.mock_client.delete_object.side_effect = ClientError(
            {'Error': {'Code': '500'}}, 'DeleteObject',
        )

        new_key = self._key_for(self.person)
        response = client_for(self.fixture['editor']).post(
            photo_endpoint(self.clan.id, self.person.id), {'key': new_key}, format='json',
        )
        self.assertEqual(200, response.status_code)
        self.person.refresh_from_db()
        self.assertEqual(new_key, self.person.photo_key)

    def test_replacing_photo_deletes_old_object_after_new_key_is_written(self):
        old_key = self._key_for(self.person)
        self.person.photo_key = old_key
        self.person.save(update_fields=['photo_key'])

        new_key = self._key_for(self.person)
        response = client_for(self.fixture['editor']).post(
            photo_endpoint(self.clan.id, self.person.id), {'key': new_key}, format='json',
        )
        self.assertEqual(200, response.status_code)
        self.person.refresh_from_db()
        self.assertEqual(new_key, self.person.photo_key)
        self.mock_client.delete_object.assert_called_once_with(Bucket='test-bucket', Key=old_key)

    def test_viewer_cannot_confirm(self):
        response = client_for(self.fixture['viewer']).post(
            photo_endpoint(self.clan.id, self.person.id), {'key': self._key_for(self.person)}, format='json',
        )
        self.assertEqual(403, response.status_code)

    def test_outsider_gets_404(self):
        response = client_for(self.fixture['outsider']).post(
            photo_endpoint(self.clan.id, self.person.id), {'key': self._key_for(self.person)}, format='json',
        )
        self.assertEqual(404, response.status_code)

    def test_generic_patch_can_no_longer_set_photo_key(self):
        """Decision 3 (phase 8): `photo_key` was removed from
        `PersonWriteSerializer._WRITE_FIELDS`. Combined with `photo_key`
        also being excluded from `services.revision._EXCLUDED_FIELDS`
        (C1 -- see `test_person_api.PersonRevisionTests`, which covers the
        `POST /restore` half), the confirm endpoint tested elsewhere in
        this class is now the ONLY legal way to set it: neither a plain
        `PATCH` nor a revision restore can.
        """
        response = client_for(self.fixture['editor']).patch(
            person_endpoint(self.clan.id, self.person.id),
            {'photo_key': 'giapha/{}/{}/hacked.jpg'.format(self.clan.id, self.person.id)},
            format='json',
        )
        self.assertEqual(200, response.status_code)
        self.person.refresh_from_db()
        self.assertEqual('', self.person.photo_key)


@override_settings(**S3_TEST_SETTINGS)
class DeletePhotoTests(MockedBotoMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_photo_delete')
        cls.clan = cls.fixture['clan']

    def test_delete_clears_photo_key_and_removes_the_object(self):
        person = build_person(self.clan, ho_ten='Có ảnh')
        key = 'giapha/{}/{}/existing.jpg'.format(self.clan.id, person.id)
        person.photo_key = key
        person.save(update_fields=['photo_key'])

        response = client_for(self.fixture['editor']).delete(photo_endpoint(self.clan.id, person.id))
        self.assertEqual(204, response.status_code)
        person.refresh_from_db()
        self.assertEqual('', person.photo_key)
        self.mock_client.delete_object.assert_called_once_with(Bucket='test-bucket', Key=key)

    def test_delete_without_an_existing_photo_does_not_call_storage(self):
        person = build_person(self.clan, ho_ten='Chưa có ảnh')
        response = client_for(self.fixture['editor']).delete(photo_endpoint(self.clan.id, person.id))
        self.assertEqual(204, response.status_code)
        self.mock_client.delete_object.assert_not_called()

    def test_outsider_gets_404(self):
        person = build_person(self.clan)
        response = client_for(self.fixture['outsider']).delete(photo_endpoint(self.clan.id, person.id))
        self.assertEqual(404, response.status_code)


@override_settings(**S3_TEST_SETTINGS)
class PhotoUrlsBatchTests(MockedBotoMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_photo_urls')
        cls.clan = cls.fixture['clan']
        cls.other_fixture = build_clan_fixture(ten_ho='Trần tộc', suffix='_photo_urls_other')

        cls.with_photo = build_person(cls.clan, ho_ten='Có ảnh')
        cls.with_photo.photo_key = 'giapha/{}/{}/a.jpg'.format(cls.clan.id, cls.with_photo.id)
        cls.with_photo.save(update_fields=['photo_key'])

        cls.without_photo = build_person(cls.clan, ho_ten='Không ảnh')
        cls.other_clan_person = build_person(cls.other_fixture['clan'], ho_ten='Người họ khác')

    def test_returns_url_for_person_with_photo_and_null_for_without(self):
        response = client_for(self.fixture['viewer']).post(
            photo_urls_endpoint(self.clan.id),
            {'person_ids': [self.with_photo.id, self.without_photo.id]}, format='json',
        )
        self.assertEqual(200, response.status_code)
        data = response.json()['data']
        self.assertEqual('https://test-bucket.example/signed', data[str(self.with_photo.id)])
        self.assertIsNone(data[str(self.without_photo.id)])

    def test_ids_from_another_clan_are_silently_dropped(self):
        response = client_for(self.fixture['viewer']).post(
            photo_urls_endpoint(self.clan.id),
            {'person_ids': [self.with_photo.id, self.other_clan_person.id]}, format='json',
        )
        self.assertEqual(200, response.status_code)
        data = response.json()['data']
        self.assertIn(str(self.with_photo.id), data)
        self.assertNotIn(str(self.other_clan_person.id), data)

    def test_over_100_ids_is_rejected(self):
        response = client_for(self.fixture['viewer']).post(
            photo_urls_endpoint(self.clan.id),
            {'person_ids': list(range(1, 102))}, format='json',
        )
        self.assertEqual(400, response.status_code)

    def test_outsider_gets_404(self):
        response = client_for(self.fixture['outsider']).post(
            photo_urls_endpoint(self.clan.id), {'person_ids': [self.with_photo.id]}, format='json',
        )
        self.assertEqual(404, response.status_code)


@override_settings(**S3_TEST_SETTINGS)
class StorageHeadNotFoundMappingTests(MockedBotoMixin, TestCase):
    """Unit-level coverage of `services.storage.head()`'s `ClientError ->
    None` mapping itself (H2/M3) -- every view-level test in this module
    hardwires `head_object` to succeed, so this is the only place that
    actually drives a `ClientError` through `head()` and checks the
    result, rather than through a view that merely reacts to `None`.
    """

    def test_404_error_code_maps_to_none(self):
        self.mock_client.head_object.side_effect = ClientError(
            {'Error': {'Code': '404'}}, 'HeadObject',
        )
        self.assertIsNone(storage.head('giapha/1/1/x.jpg'))

    def test_403_error_code_also_maps_to_none(self):
        """M3: a credential without `s3:ListBucket` gets 403, not 404, for
        a key that was never uploaded -- `head()` must treat that the same
        as a 404 or the H2 guard in `views/photo.py` becomes unreachable
        behind that (common least-privilege) permission setup.
        """
        self.mock_client.head_object.side_effect = ClientError(
            {'Error': {'Code': '403'}}, 'HeadObject',
        )
        self.assertIsNone(storage.head('giapha/1/1/x.jpg'))

    def test_other_error_codes_still_propagate(self):
        """Guard against over-widening the mapping -- a genuine fault
        (wrong credentials, provider outage) must still raise, not
        silently read as "not found".
        """
        self.mock_client.head_object.side_effect = ClientError(
            {'Error': {'Code': '500'}}, 'HeadObject',
        )
        with self.assertRaises(ClientError):
            storage.head('giapha/1/1/x.jpg')


@override_settings(**S3_TEST_SETTINGS)
class PhotoUrlListScopeTests(MockedBotoMixin, TestCase):
    """H3: `photo_url` is detail-only per the phase-08 spec -- the list
    endpoint (used with `many=True`, up to 200 rows) must never presign,
    while the detail endpoint for the SAME person still does.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_photo_scope')
        cls.clan = cls.fixture['clan']
        cls.person = build_person(cls.clan, ho_ten='Có ảnh cho scope test')
        cls.person.photo_key = 'giapha/{}/{}/a.jpg'.format(cls.clan.id, cls.person.id)
        cls.person.save(update_fields=['photo_key'])

    def test_list_endpoint_returns_null_photo_url(self):
        response = client_for(self.fixture['viewer']).get(person_list_endpoint(self.clan.id))
        self.assertEqual(200, response.status_code)
        rows = {row['id']: row for row in response.json()['data']}
        self.assertIsNone(rows[self.person.id]['photo_url'])
        self.mock_client.generate_presigned_url.assert_not_called()

    def test_detail_endpoint_still_presigns_photo_url_for_the_same_person(self):
        response = client_for(self.fixture['viewer']).get(person_endpoint(self.clan.id, self.person.id))
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            'https://test-bucket.example/signed', response.json()['data']['photo_url'],
        )
