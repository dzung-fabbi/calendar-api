"""`/api/appointment-date` -- the replace-list contract and its validation.

Ownership is covered by `test_security.py`; this file is about the payload:
`before_days` as whole days both ways, and the 400s.
"""

import datetime as dt

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from apis.models import AppointmentDate

URL = '/api/appointment-date'


class AppointmentDateApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='driver', password='pw')

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def post(self, body):
        return self.client.post(URL, body, format='json')

    def test_before_days_is_whole_days_in_both_directions(self):
        response = self.post([{'name': 'Đăng kiểm xe', 'date': '2026-10-01', 'before_days': 3}])
        self.assertEqual(201, response.status_code)
        item = response.json()['data'][0]
        self.assertEqual(3, item['before_days'])
        self.assertEqual(3, item['convert_time'])
        self.assertEqual(
            dt.timedelta(days=3), AppointmentDate.objects.get(id=item['id']).before_days,
        )

    def test_reposting_the_response_round_trips(self):
        """The old serializer rendered `"3 00:00:00"`, which the view then fed
        to `int()` -- a client saving what it had just loaded got a 500."""
        first = self.post([{'name': 'Đăng kiểm xe', 'date': '2026-10-01', 'before_days': 3}])
        second = self.post(first.json()['data'])
        self.assertEqual(201, second.status_code)
        self.assertEqual(first.json()['data'], second.json()['data'])

    def test_before_days_defaults_to_zero(self):
        response = self.post([{'name': 'x', 'date': '2026-10-01'}])
        self.assertEqual(0, response.json()['data'][0]['before_days'])

    def test_before_days_out_of_range_or_fractional_is_400(self):
        for value in (-1, 366, 1.5, '3 00:00:00', 'abc'):
            response = self.post([{'name': 'x', 'date': '2026-10-01', 'before_days': value}])
            self.assertEqual(400, response.status_code, value)
            self.assertIn('before_days', response.json()[0])

    def test_date_is_required(self):
        for body in ([{'name': 'x', 'before_days': 1}], [{'name': 'x', 'date': None}]):
            response = self.post(body)
            self.assertEqual(400, response.status_code)
            self.assertIn('date', response.json()[0])

    def test_unknown_id_is_400_and_changes_nothing(self):
        kept = AppointmentDate.objects.create(name='Giữ lại', date='2026-11-01', user=self.user)
        response = self.post([
            {'id': kept.id, 'name': 'Đổi tên', 'date': '2026-11-02', 'before_days': 1},
            {'id': 999999, 'name': 'Không tồn tại', 'date': '2026-10-01', 'before_days': 1},
        ])
        self.assertEqual(400, response.status_code)
        self.assertIn('999999', response.json()['detail'])
        kept.refresh_from_db()
        self.assertEqual('Giữ lại', kept.name)
        self.assertEqual(1, AppointmentDate.objects.filter(user=self.user).count())

    def test_duplicate_id_in_one_batch_is_400(self):
        row = AppointmentDate.objects.create(name='Một', date='2026-11-01', user=self.user)
        response = self.post([
            {'id': row.id, 'name': 'A', 'date': '2026-11-01'},
            {'id': row.id, 'name': 'B', 'date': '2026-11-01'},
        ])
        self.assertEqual(400, response.status_code)
        row.refresh_from_db()
        self.assertEqual('Một', row.name)

    def test_update_create_and_delete_in_one_post(self):
        keep = AppointmentDate.objects.create(name='Sửa', date='2026-11-01', user=self.user)
        AppointmentDate.objects.create(name='Xoá', date='2026-11-01', user=self.user)
        response = self.post([
            {'id': keep.id, 'name': 'Đã sửa', 'date': '2026-11-03', 'before_days': 2},
            {'name': 'Mới', 'date': '2026-12-01', 'before_days': 5},
        ])
        self.assertEqual(201, response.status_code)
        rows = {row.name: row for row in AppointmentDate.objects.filter(user=self.user)}
        self.assertEqual({'Đã sửa', 'Mới'}, set(rows))
        self.assertEqual(dt.date(2026, 11, 3), rows['Đã sửa'].date)
        self.assertEqual(dt.timedelta(days=2), rows['Đã sửa'].before_days)
        self.assertEqual(keep.id, rows['Đã sửa'].id)

    def test_empty_list_clears_the_callers_rows(self):
        AppointmentDate.objects.create(name='x', date='2026-11-01', user=self.user)
        response = self.post([])
        self.assertEqual(201, response.status_code)
        self.assertEqual([], response.json()['data'])
        self.assertFalse(AppointmentDate.objects.filter(user=self.user).exists())
