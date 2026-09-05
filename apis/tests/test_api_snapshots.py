"""Contract tests for every route in apis/urls.py.

These freeze the *shape* of each response so the refactor cannot silently drop
or rename a field. Values that the refactor deliberately corrects are asserted
separately, in the service-level unit tests.
"""

import json

from django.test import TestCase
from rest_framework.test import APIClient

from apis.tests import factories
from apis.tests.shape import SnapshotMixin


class ApiShapeTests(SnapshotMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = factories.build_fixture()

    def setUp(self):
        self.client = APIClient()

    def authenticated_client(self):
        client = APIClient()
        client.force_authenticate(user=self.fixture["user"])
        return client

    # -- public read endpoints ------------------------------------------------

    def test_tiet_khi(self):
        response = self.client.get("/api/tiet-khi", {"tiet_khi": factories.TIET_KHI})
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["data"], "fixture should match a TietKhi row")
        self.assert_shape_matches("tiet_khi", response.json())

    def test_calendar(self):
        payload = json.dumps([
            {"month": factories.MONTH, "lunar_day": factories.LUNAR_DAY},
            {"month": factories.MONTH, "lunar_day": "ẤT SỬU"},
            # A day with no HiepKy row: exercises the empty-string branch.
            {"month": 12, "lunar_day": factories.LUNAR_DAY},
        ])
        response = self.client.get("/api/calendar", {"data": payload})
        self.assertEqual(200, response.status_code)
        data = response.json()["data"]
        self.assertEqual(3, len(data))
        self.assertTrue(data[0]["good_stars"], "first day should carry good stars")
        self.assertEqual("", data[2]["good_stars"], "missing day should be blank")
        self.assert_shape_matches("calendar", response.json())

    def test_home(self):
        response = self.client.get("/api/home", {
            "lunar_date": "{}-03-01 00:00:00".format(self.fixture["tiet_khi"].year),
            "lunar_day": factories.LUNAR_DAY,
            "tiet_khi": factories.TIET_KHI,
            "month": factories.MONTH,
        })
        self.assertEqual(200, response.status_code)
        data = response.json()["data"]
        self.assertTrue(data["hiep_ky"], "fixture should match a HiepKy row")
        self.assertTrue(data["tiet_khi"], "fixture should match a TietKhi row")
        self.assertTrue(data["hour_in_days"], "fixture should match a HourInDay row")
        self.assertTrue(data["quy_nhan"], "fixture should match QuyNhan rows")
        self.assertTrue(data["tu_dai"], "fixture should match TuDaiCatThoi rows")
        self.assert_shape_matches("home", response.json())

    def test_than_sat(self):
        response = self.client.get("/api/than-sat", {"year": factories.THAN_SAT_YEAR})
        self.assertEqual(200, response.status_code)
        data = response.json()
        self.assertTrue(data["than_sat_by_year"]["than_sat_sao"])
        self.assertTrue(data["than_sat_by_month"]["month_01"])
        self.assertTrue(data["than_sat_by_month"]["month_12"])
        self.assert_shape_matches("than_sat", data)

    def test_so_hoc(self):
        response = self.client.get("/api/so-hoc", {
            "birth_day": "15081990",
            "full_name": "Nguyễn Văn An",
            "phone": "0912345678",
        })
        self.assertEqual(200, response.status_code)
        self.assert_shape_matches("so_hoc", response.json())

    def test_date_good_by_work(self):
        response = self.client.get("/api/get-date-good-by-work", {
            "work": factories.WORK,
            "month": factories.MONTH,
            "year": 2026,
        })
        self.assertEqual(200, response.status_code)
        data = response.json()["data"]
        self.assertTrue(data, "a lunar month must contain matching can-chi days")
        self.assert_shape_matches("date_good_by_work", response.json())

    def test_config(self):
        response = self.client.get("/api/get-config")
        self.assertEqual(200, response.status_code)
        self.assert_shape_matches("config", response.json())

    # -- write / authenticated endpoints --------------------------------------

    def test_book_calendar(self):
        response = self.client.post("/api/book-calendar", {
            "work": "Cưới hỏi",
            "date": "2026-10-01",
            "email": "khach@example.com",
        }, format="json")
        self.assertEqual(201, response.status_code)
        self.assert_shape_matches("book_calendar", response.json())

    def test_appointment_date_get(self):
        response = self.authenticated_client().get("/api/appointment-date")
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["data"])
        self.assert_shape_matches("appointment_date", response.json())

    def test_bank(self):
        response = self.authenticated_client().get("/api/get-bank")
        self.assertEqual(200, response.status_code)
        self.assert_shape_matches("bank", response.json())

    def test_user(self):
        response = self.authenticated_client().get("/api/get-user")
        self.assertEqual(200, response.status_code)
        self.assert_shape_matches("user", response.json())
