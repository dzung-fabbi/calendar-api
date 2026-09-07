"""`GET`/`PATCH /api/me` (and its original name, `/api/get-user`)."""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from apis.models import UserProfile

ME = '/api/me'
LEGACY = '/api/get-user'


class ProfileAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='nguoi.dung@example.com',
            email='nguoi.dung@example.com',
            password='MatKhau!2026',
            first_name='An',
            last_name='Nguyễn',
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def patch(self, **body):
        return self.client.patch(ME, body, format='json')

    # -- reading ----------------------------------------------------------

    def test_get_returns_user_with_nested_profile(self):
        payload = self.client.get(ME).json()['data']
        self.assertEqual('nguoi.dung@example.com', payload['email'])
        self.assertEqual({'phone': '', 'birth_date': None, 'avatar_url': ''},
                         payload['profile'])

    def test_legacy_path_returns_the_same_payload(self):
        self.assertEqual(self.client.get(ME).json(), self.client.get(LEGACY).json())

    def test_get_leaks_no_privileged_field(self):
        payload = self.client.get(ME).json()['data']
        for field in ('password', 'is_staff', 'is_superuser', 'is_active',
                      'groups', 'user_permissions'):
            self.assertNotIn(field, payload)
        for field in ('is_free', 'expiry_datetime'):
            self.assertNotIn(field, payload['profile'])

    def test_unauthenticated_is_401(self):
        self.assertEqual(401, APIClient().get(ME).status_code)
        self.assertEqual(401, APIClient().patch(ME, {}, format='json').status_code)

    # -- writing ----------------------------------------------------------

    def test_patch_updates_every_writable_field(self):
        response = self.patch(
            first_name='Bình', last_name='Trần', phone='0912345678',
            birth_date='1990-01-31', avatar_url='https://cdn.example.com/a.png',
        )
        self.assertEqual(200, response.status_code, response.content)

        self.user.refresh_from_db()
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual('Bình', self.user.first_name)
        self.assertEqual('Trần', self.user.last_name)
        self.assertEqual('0912345678', profile.phone)
        self.assertEqual('1990-01-31', str(profile.birth_date))
        self.assertEqual('https://cdn.example.com/a.png', profile.avatar_url)

    def test_absent_key_leaves_the_stored_value_alone(self):
        self.patch(phone='0912345678')
        self.patch(first_name='Bình')
        self.assertEqual('0912345678', UserProfile.objects.get(user=self.user).phone)

    def test_blank_phone_clears_it(self):
        self.patch(phone='0912345678')
        self.patch(phone='')
        self.assertEqual('', UserProfile.objects.get(user=self.user).phone)

    def test_empty_body_is_a_no_op_200(self):
        self.assertEqual(200, self.patch().status_code)

    def test_profile_row_is_created_when_missing(self):
        """Accounts older than migration 0055 have no profile row -- the
        creating signal only fires on insert."""
        UserProfile.objects.filter(user=self.user).delete()
        self.assertEqual({'phone': '', 'birth_date': None, 'avatar_url': ''},
                         self.client.get(ME).json()['data']['profile'])

        self.assertEqual(200, self.patch(phone='0912345678').status_code)
        self.assertEqual('0912345678', UserProfile.objects.get(user=self.user).phone)

    # -- validation -------------------------------------------------------

    def test_phone_is_normalised(self):
        for sent in ('+84 912 345 678', '0912-345-678'):
            response = self.patch(phone=sent)
            self.assertEqual(200, response.status_code, response.content)

    def test_invalid_phone_is_rejected(self):
        response = self.patch(phone='khong-phai-so')
        self.assertEqual(400, response.status_code)
        self.assertIn('phone', response.json())

    def test_future_birth_date_is_rejected(self):
        response = self.patch(birth_date='2999-01-01')
        self.assertEqual(400, response.status_code)
        self.assertIn('birth_date', response.json())

    def test_dangerous_avatar_schemes_are_rejected(self):
        """A stored `javascript:` URL is handed straight back to whichever
        client renders the profile -- stored XSS delivered through the API."""
        for url in ('javascript:alert(1)', 'data:text/html,<script>x</script>'):
            response = self.patch(avatar_url=url)
            self.assertEqual(400, response.status_code, url)
            self.assertIn('avatar_url', response.json())

    def test_non_bmp_name_is_a_400_not_a_500(self):
        response = self.patch(first_name='An 😀')
        self.assertEqual(400, response.status_code, response.content)
        self.assertIn('first_name', response.json())

    # -- mass assignment --------------------------------------------------

    def test_identity_and_privilege_fields_are_ignored(self):
        """`email`/`username` are the login identity and there is no address
        verification, so accepting a change would let a stolen token repoint
        the account at the attacker's mailbox and lock the owner out for good.
        The privilege and billing flags must be equally unreachable."""
        response = self.patch(
            email='ke.tan.cong@example.com',
            username='ke.tan.cong@example.com',
            is_staff=True, is_superuser=True, is_active=False,
            password='bikiem soat', is_free=1, expiry_datetime='2099-01-01',
        )
        self.assertEqual(200, response.status_code, response.content)

        self.user.refresh_from_db()
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual('nguoi.dung@example.com', self.user.email)
        self.assertEqual('nguoi.dung@example.com', self.user.username)
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertTrue(self.user.is_active)
        self.assertTrue(self.user.check_password('MatKhau!2026'))
        self.assertEqual(0, profile.is_free)
        self.assertIsNone(profile.expiry_datetime)
