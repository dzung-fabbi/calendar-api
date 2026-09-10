"""Regression tests for the access-control fixes."""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from apis.models import AppointmentDate


class AppointmentOwnershipTests(TestCase):
    """A caller must only ever see and change their own appointments."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username='owner', password='pw')
        cls.attacker = User.objects.create_user(username='attacker', password='pw')
        cls.owner_row = AppointmentDate.objects.create(
            name='Riêng tư', date='2026-06-01', user=cls.owner,
        )

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_post_cannot_overwrite_another_users_appointment(self):
        response = self.client_for(self.attacker).post(
            "/api/appointment-date",
            [{"id": self.owner_row.id, "name": "Đã bị sửa", "date": "2026-07-01",
              "before_days": 1}],
            format="json",
        )
        # Same 400 as for an id that does not exist: the response must not
        # confirm that somebody else's row is there.
        self.assertEqual(400, response.status_code)
        self.assertNotIn('Riêng tư', response.content.decode())

        self.owner_row.refresh_from_db()
        self.assertEqual('Riêng tư', self.owner_row.name)
        self.assertEqual('2026-06-01', str(self.owner_row.date))

    def test_post_cannot_delete_another_users_appointments(self):
        self.client_for(self.attacker).post(
            "/api/appointment-date", [], format="json",
        )
        self.assertTrue(
            AppointmentDate.objects.filter(id=self.owner_row.id).exists(),
            "posting an empty list must only clear the caller's own rows",
        )

    def test_post_cannot_assign_rows_to_another_user(self):
        response = self.client_for(self.attacker).post(
            "/api/appointment-date",
            [{"name": "Gán sai chủ", "date": "2026-08-01", "before_days": 2,
              "user_id": self.owner.id}],
            format="json",
        )
        self.assertEqual(201, response.status_code)
        created = AppointmentDate.objects.get(name='Gán sai chủ')
        self.assertEqual(
            self.attacker.id, created.user_id,
            "the row must belong to the caller, not to the posted user_id",
        )

    def test_replaces_only_callers_own_rows(self):
        client = self.client_for(self.owner)
        response = client.post(
            "/api/appointment-date",
            [{"name": "Lịch mới", "date": "2026-09-01", "before_days": 3}],
            format="json",
        )
        self.assertEqual(201, response.status_code)
        names = set(
            AppointmentDate.objects.filter(user=self.owner).values_list('name', flat=True)
        )
        self.assertEqual({'Lịch mới'}, names)


class UserEndpointTests(TestCase):
    """The user endpoint must not leak credentials or permission flags."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='someone', password='pw', email='someone@example.com',
        )

    def test_does_not_expose_password_or_privilege_flags(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        data = client.get("/api/get-user").json()["data"]

        for leaked in ('password', 'is_superuser', 'is_staff', 'user_permissions', 'groups'):
            self.assertNotIn(leaked, data)
        self.assertEqual('someone', data['username'])
