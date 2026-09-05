"""Query-count ratchet.

Each endpoint has a recorded budget. A request may use fewer queries than its
budget but never more, so an accidental N+1 reintroduction fails the build.
After a round of optimisation, lower the numbers in
``snapshots/query_budgets.json`` to lock the win in.
"""

import json

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apis.tests import factories
from apis.tests.shape import load_snapshot, save_snapshot

BUDGETS = "query_budgets"


class QueryCountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = factories.build_fixture()

    def setUp(self):
        self.client = APIClient()

    def assert_within_budget(self, name, client, path, params=None):
        with CaptureQueriesContext(connection) as captured:
            response = client.get(path, params or {})
        self.assertEqual(200, response.status_code)

        count = len(captured.captured_queries)
        budgets = load_snapshot(BUDGETS) or {}
        if name not in budgets:
            budgets[name] = count
            save_snapshot(BUDGETS, budgets)
            self.skipTest(
                "Recorded query budget {}={}. Re-run to assert it.".format(name, count)
            )

        self.assertLessEqual(
            count,
            budgets[name],
            "{} used {} queries, budget is {}. If this is an intended "
            "regression, justify it; otherwise it is an N+1.".format(
                name, count, budgets[name]
            ),
        )

    def test_calendar_full_month(self):
        payload = json.dumps([
            {"month": factories.MONTH, "lunar_day": day}
            for day in factories.CAN_CHI[:30]
        ])
        self.assert_within_budget(
            "calendar_30_days", self.client, "/api/calendar", {"data": payload}
        )

    def test_home(self):
        self.assert_within_budget("home", self.client, "/api/home", {
            "lunar_date": "{}-03-01 00:00:00".format(self.fixture["tiet_khi"].year),
            "lunar_day": factories.LUNAR_DAY,
            "tiet_khi": factories.TIET_KHI,
            "month": factories.MONTH,
        })

    def test_than_sat(self):
        self.assert_within_budget(
            "than_sat", self.client, "/api/than-sat",
            {"year": factories.THAN_SAT_YEAR},
        )

    def test_date_good_by_work(self):
        self.assert_within_budget(
            "date_good_by_work", self.client, "/api/get-date-good-by-work",
            {"work": factories.WORK, "month": factories.MONTH, "year": 2026},
        )

    def test_tiet_khi(self):
        self.assert_within_budget(
            "tiet_khi", self.client, "/api/tiet-khi",
            {"tiet_khi": factories.TIET_KHI},
        )

    def test_config(self):
        self.assert_within_budget("config", self.client, "/api/get-config")

    def test_appointment_date(self):
        client = APIClient()
        client.force_authenticate(user=self.fixture["user"])
        self.assert_within_budget(
            "appointment_date", client, "/api/appointment-date"
        )
