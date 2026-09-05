"""Exact-value golden tests for the deterministic read endpoints.

Recorded from the pre-refactor code so that the package split, the serializer
rewrite and the query optimisation can be proven behaviour-neutral. When a
deliberate logic fix changes one of these, the golden file is re-recorded in
the same commit as the fix, and the diff documents exactly what changed.

Excluded on purpose: /api/get-bank (generates a random code) and
/api/book-calendar (echoes the request).
"""

import json

from django.test import TestCase
from rest_framework.test import APIClient

from apis.tests import factories
from apis.tests.shape import SnapshotMixin


class ApiValueTests(SnapshotMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = factories.build_fixture()

    def setUp(self):
        self.client = APIClient()

    def test_tiet_khi_values(self):
        response = self.client.get("/api/tiet-khi", {"tiet_khi": factories.TIET_KHI})
        self.assert_value_matches("values_tiet_khi", response.json())

    def test_calendar_values(self):
        payload = json.dumps([
            {"month": factories.MONTH, "lunar_day": factories.LUNAR_DAY},
            {"month": factories.MONTH, "lunar_day": "ẤT SỬU"},
            {"month": 12, "lunar_day": factories.LUNAR_DAY},
        ])
        response = self.client.get("/api/calendar", {"data": payload})
        self.assert_value_matches("values_calendar", response.json())

    def test_home_values(self):
        response = self.client.get("/api/home", {
            "lunar_date": "{}-03-01 00:00:00".format(self.fixture["tiet_khi"].year),
            "lunar_day": factories.LUNAR_DAY,
            "tiet_khi": factories.TIET_KHI,
            "month": factories.MONTH,
        })
        self.assert_value_matches("values_home", response.json())

    def test_than_sat_values(self):
        response = self.client.get("/api/than-sat", {"year": factories.THAN_SAT_YEAR})
        self.assert_value_matches("values_than_sat", response.json())

    def test_so_hoc_values(self):
        response = self.client.get("/api/so-hoc", {
            "birth_day": "15081990",
            "full_name": "Nguyễn Văn An",
            "phone": "0912345678",
        })
        self.assert_value_matches("values_so_hoc", response.json())

    def test_date_good_by_work_values(self):
        response = self.client.get("/api/get-date-good-by-work", {
            "work": factories.WORK,
            "month": factories.MONTH,
            "year": 2026,
        })
        self.assert_value_matches("values_date_good_by_work", response.json())

    def test_config_values(self):
        response = self.client.get("/api/get-config")
        self.assert_value_matches("values_config", response.json())

    def test_appointment_date_values(self):
        client = APIClient()
        client.force_authenticate(user=self.fixture["user"])
        response = client.get("/api/appointment-date")
        self.assert_value_matches("values_appointment_date", response.json())
