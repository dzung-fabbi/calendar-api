"""`POST /api/auth/register`.

Users are created with `User.objects.create_user` and NO explicit id -- unlike
`factories.build_fixture`, which pins ids for the AUTO_INCREMENT reason
documented in `apis/tests/factories.py`. Same convention as `test_security.py`.
"""

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

URL = '/api/auth/register'
STRONG = 'Kh0ngDeDoan!2026'


class RegisterAPITests(TestCase):
    def setUp(self):
        # `ScopedRateThrottle` state lives in the cache and outlives a test, so
        # without this the 11th register in the whole MODULE is a 429 and which
        # test sees it depends on execution order.
        cache.clear()
        self.client = APIClient()

    def post(self, **overrides):
        body = {'email': 'nguoi.dung@example.com', 'password': STRONG,
                'first_name': 'An', 'last_name': 'Nguyễn'}
        body.update(overrides)
        return self.client.post(URL, body, format='json')

    def test_creates_active_user_with_email_as_username(self):
        response = self.post()
        self.assertEqual(201, response.status_code, response.content)

        user = User.objects.get(email='nguoi.dung@example.com')
        self.assertEqual('nguoi.dung@example.com', user.username)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_email_is_normalised_to_lower_case(self):
        response = self.post(email='Nguoi.Dung@Example.COM')
        self.assertEqual(201, response.status_code, response.content)
        self.assertTrue(User.objects.filter(username='nguoi.dung@example.com').exists())

    def test_password_is_stored_hashed(self):
        self.post()
        user = User.objects.get(username='nguoi.dung@example.com')
        self.assertTrue(user.check_password(STRONG))
        self.assertNotEqual(STRONG, user.password)

    def test_profile_row_is_created(self):
        self.post()
        user = User.objects.get(username='nguoi.dung@example.com')
        self.assertTrue(hasattr(user, 'profile'))

    def test_response_leaks_no_privileged_field(self):
        payload = self.post().json()['data']
        for field in ('password', 'is_staff', 'is_superuser', 'is_active',
                      'groups', 'user_permissions'):
            self.assertNotIn(field, payload)
        for field in ('is_free', 'expiry_datetime'):
            self.assertNotIn(field, payload['profile'])

    def test_duplicate_email_is_rejected_without_creating_a_second_user(self):
        self.post()
        response = self.post()
        self.assertEqual(400, response.status_code)
        self.assertIn('email', response.json())
        self.assertEqual(1, User.objects.filter(username='nguoi.dung@example.com').count())

    def test_duplicate_differing_only_in_case_is_a_400_not_a_500(self):
        """`utf8_unicode_ci` makes the username index case-insensitive, so the
        database would reject this even if the serializer did not."""
        self.post()
        response = self.post(email='NGUOI.DUNG@EXAMPLE.COM')
        self.assertEqual(400, response.status_code, response.content)

    def test_email_longer_than_the_username_column_is_a_400(self):
        """`auth_user.username` is 150 chars, `email` is 254. The address
        becomes the username, so the shorter column is the real limit -- left
        unchecked this is a DataError 500, not a 400."""
        response = self.post(email='{}@example.com'.format('a' * 200))
        self.assertEqual(400, response.status_code, response.content)
        self.assertIn('email', response.json())

    def test_weak_password_is_rejected(self):
        # Asserts the field key only. The message text is Django's own
        # translation catalogue (LANGUAGE_CODE='vi'), not our contract.
        response = self.post(password='123456')
        self.assertEqual(400, response.status_code)
        self.assertIn('password', response.json())

    def test_password_too_similar_to_the_email_is_rejected(self):
        """Proves an unsaved `User` is handed to `validate_password`.

        `UserAttributeSimilarityValidator` is a SILENT no-op when `user=None`,
        so the naive call would let this through.
        """
        response = self.post(email='nguyenvanan@example.com', password='nguyenvanan')
        self.assertEqual(400, response.status_code, response.content)
        self.assertIn('password', response.json())

    def test_non_bmp_name_is_a_400_not_a_500(self):
        """MySQL 5.7 runs here with 3-byte `utf8`, which cannot store an emoji
        at all -- it raises `Incorrect string value` at INSERT."""
        response = self.post(first_name='An 😀')
        self.assertEqual(400, response.status_code, response.content)
        self.assertIn('first_name', response.json())

    def test_names_are_optional(self):
        response = self.post(first_name='', last_name='')
        self.assertEqual(201, response.status_code, response.content)
