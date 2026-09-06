"""Shape contract tests for the photo endpoints (phase 8) and the public
share-link + public tree/detail endpoints (phase 9). See
`test_api_snapshots.py`'s module docstring for the shared rationale (sibling
split of the same suite, kept under the file-size guideline).

`boto3` is mocked exactly like `test_photo_api.py` -- see that file's module
docstring for why (nothing here touches the network).
"""

import uuid
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.services import storage
from giapha.tests.factories import build_clan_fixture, build_person
from giapha.tests.public_helpers import PublicEndpointTestCase, enable_public_link
from giapha.tests.shape import SnapshotMixin

S3_TEST_SETTINGS = dict(
    S3_ENDPOINT_URL='', S3_BUCKET='test-bucket', S3_ACCESS_KEY_ID='test-key',
    S3_SECRET_ACCESS_KEY='test-secret', S3_REGION='auto',
)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@override_settings(**S3_TEST_SETTINGS)
class PhotoSnapshotTests(SnapshotMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_snap_photo')
        cls.clan = cls.fixture['clan']
        cls.person = build_person(cls.clan, ho_ten='Ảnh')

    def setUp(self):
        super().setUp()
        storage.reset_client_cache()
        patcher = mock.patch('giapha.services.storage.boto3.client')
        mock_client_factory = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_client = mock.Mock()
        mock_client_factory.return_value = self.mock_client
        self.mock_client.generate_presigned_url.return_value = 'https://test-bucket.example/signed'
        self.mock_client.head_object.return_value = {'ContentLength': 1000, 'ContentType': 'image/jpeg'}

    def test_photo_upload_url(self):
        response = client_for(self.fixture['editor']).post(
            reverse('person-photo-upload-url', kwargs={'clan_id': self.clan.id, 'person_id': self.person.id}),
            {'content_type': 'image/jpeg', 'size': 1000}, format='json',
        )
        self.assertEqual(200, response.status_code)
        self.assert_shape_matches('photo_upload_url', response.json())

    def test_photo_confirm(self):
        # `_KEY_RE` (views/photo.py) requires a 32-hex-char basename, not an
        # arbitrary filename -- matches the shape `PersonPhotoUploadUrlAPIView`
        # actually mints.
        key = 'giapha/{}/{}/{}.jpg'.format(self.clan.id, self.person.id, uuid.uuid4().hex)
        response = client_for(self.fixture['editor']).post(
            reverse('person-photo', kwargs={'clan_id': self.clan.id, 'person_id': self.person.id}),
            {'key': key}, format='json',
        )
        self.assertEqual(200, response.status_code)
        self.assert_shape_matches('photo_confirm', response.json())

    def test_photo_urls_batch(self):
        self.person.photo_key = 'giapha/{}/{}/a.jpg'.format(self.clan.id, self.person.id)
        self.person.save(update_fields=['photo_key'])
        response = client_for(self.fixture['viewer']).post(
            reverse('clan-photo-urls', kwargs={'clan_id': self.clan.id}),
            {'person_ids': [self.person.id]}, format='json',
        )
        self.assertEqual(200, response.status_code)
        # Values only, NOT the whole dict: keys are Person ids, which are
        # MySQL AUTO_INCREMENT values and therefore not stable across runs
        # (see `apis/tests/factories.py`'s docstring on the same class of
        # problem) -- a shape snapshot keyed on them would fail on an
        # unrelated test creating an extra row earlier in the same run.
        self.assert_shape_matches('photo_urls_batch', list(response.json()['data'].values()))


class PublicLinkSnapshotTests(SnapshotMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_snap_public_link')
        cls.clan = cls.fixture['clan']

    def test_public_link_create(self):
        response = client_for(self.fixture['owner']).post(
            reverse('clan-public-link', kwargs={'clan_id': self.clan.id}),
        )
        self.assertEqual(200, response.status_code)
        self.assert_shape_matches('public_link_create', response.json())


class PublicSurfaceSnapshotTests(SnapshotMixin, PublicEndpointTestCase):
    """`PublicEndpointTestCase` (not plain `TestCase`): clears the throttle
    cache in `setUp` -- see its docstring. Without it, an earlier public-
    endpoint test class in the same run can exhaust this scope's bucket
    first and turn every request here into a 429.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_snap_public_surface')
        cls.clan = cls.fixture['clan']
        cls.living = build_person(cls.clan, ho_ten='Còn sống')
        cls.dead = build_person(
            cls.clan, ho_ten='Đã mất', death_lunar_day=1, death_lunar_month=1,
        )
        cls.slug = enable_public_link(cls.clan)

    def test_public_tree(self):
        body = APIClient().get(reverse('public-clan-tree', kwargs={'slug': self.slug})).json()
        self.assert_shape_matches('public_tree', body)

    def test_public_person_detail_living(self):
        body = APIClient().get(
            reverse('public-person-detail', kwargs={'slug': self.slug, 'person_id': self.living.id}),
        ).json()
        self.assert_shape_matches('public_person_detail_living', body)

    def test_public_person_detail_dead(self):
        body = APIClient().get(
            reverse('public-person-detail', kwargs={'slug': self.slug, 'person_id': self.dead.id}),
        ).json()
        self.assert_shape_matches('public_person_detail_dead', body)
