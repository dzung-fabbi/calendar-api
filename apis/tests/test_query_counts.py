"""Query-count ratchet.

Each endpoint has a recorded budget. A request may use fewer queries than its
budget but never more, so an accidental N+1 reintroduction fails the build.
After a round of optimisation, lower the numbers in
``snapshots/query_budgets.json`` to lock the win in.
"""

import json
from unittest import mock

from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apis.services import storage
from apis.tests import factories
from apis.tests.shape import load_snapshot, save_snapshot
from apis.tests.test_file_upload_api import S3_TEST_SETTINGS, a_key

BUDGETS = "query_budgets"


class QueryCountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = factories.build_fixture()

    def setUp(self):
        self.client = APIClient()

    def assert_within_budget(self, name, client, path, params=None):
        self._assert_call_within_budget(
            name, lambda: client.get(path, params or {}), 200,
        )

    def assert_post_within_budget(self, name, client, path, body, expected_status=200):
        """POST variant. The account endpoints are all writes, so the ratchet
        would not cover any of them without this."""
        self._assert_call_within_budget(
            name, lambda: client.post(path, body, format="json"), expected_status,
        )

    def assert_patch_within_budget(self, name, client, path, body):
        self._assert_call_within_budget(
            name, lambda: client.patch(path, body, format="json"), 200,
        )

    def _assert_call_within_budget(self, name, call, expected_status):
        with CaptureQueriesContext(connection) as captured:
            response = call()
        self.assertEqual(expected_status, response.status_code, response.content)

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

    # -- account endpoints ------------------------------------------------
    #
    # `get_user` was missing entirely despite docs/codebase-summary.md
    # publishing a budget of 1 for it -- the one endpoint whose shape this
    # feature changes (it now nests `profile`) had no ratchet at all.

    def test_get_user(self):
        client = APIClient()
        client.force_authenticate(user=self.fixture["user"])
        self.assert_within_budget("get_user", client, "/api/get-user")

    def test_me_patch(self):
        client = APIClient()
        client.force_authenticate(user=self.fixture["user"])
        self.assert_patch_within_budget(
            "me_patch", client, "/api/me", {"first_name": "An"},
        )

    def test_auth_register(self):
        self.assert_post_within_budget(
            "auth_register",
            APIClient(),
            "/api/auth/register",
            {"email": "budget@example.com", "password": "Kh0ngDeDoan!2026"},
            expected_status=201,
        )

    # Login/refresh/logout. The user's password is reset to a known value
    # because `factories.build_fixture` may not store one `authenticate()`
    # accepts. `cache.clear()`: both scopes are per-IP throttled.
    def _login_body(self):
        cache.clear()
        user = self.fixture["user"]
        user.set_password("MatKhauCu!2026")
        user.save()
        return {"username": user.username, "password": "MatKhauCu!2026"}

    def test_auth_login(self):
        self.assert_post_within_budget(
            "auth_login", APIClient(), "/api/auth/login", self._login_body(),
        )

    def test_auth_refresh(self):
        # Budget 5 = 3 real queries (SELECT row, DELETE it, INSERT the new one)
        # + the SAVEPOINT/RELEASE pair that the view's `transaction.atomic()`
        # emits under TestCase's outer transaction. In production that pair is
        # BEGIN/COMMIT and is not an N+1.
        tokens = APIClient().post("/api/auth/login", self._login_body(), format="json").json()
        self.assert_post_within_budget(
            "auth_refresh", APIClient(), "/api/auth/refresh",
            {"refresh_token": tokens["refresh_token"]},
        )

    def test_auth_logout(self):
        tokens = APIClient().post("/api/auth/login", self._login_body(), format="json").json()
        self.assert_post_within_budget(
            "auth_logout", APIClient(), "/api/auth/logout",
            {"refresh_token": tokens["refresh_token"]}, expected_status=204,
        )

    def test_auth_forgot_password(self):
        self.assert_post_within_budget(
            "auth_forgot_password",
            APIClient(),
            "/api/auth/forgot-password",
            {"email": self.fixture["user"].email or "khong.co@example.com"},
        )

    def test_auth_change_password(self):
        user = self.fixture["user"]
        user.set_password("MatKhauCu!2026")
        user.save()
        client = APIClient()
        client.force_authenticate(user=user)
        self.assert_post_within_budget(
            "auth_change_password",
            client,
            "/api/auth/change-password",
            {"current_password": "MatKhauCu!2026", "new_password": "MatKhauMoi!2026"},
        )

    # The two file endpoints touch no model at all -- budget 0. They need
    # `boto3` mocked and `S3_*` set, or they would answer 503 instead of 200
    # and the ratchet would be measuring the error path.
    def _mocked_storage(self):
        cache.clear()
        storage.reset_client_cache()
        # Also on the way OUT: without this the Mock built here stays in the
        # module-level client cache after `patcher.stop()`, for whatever runs
        # next in the process.
        self.addCleanup(storage.reset_client_cache)
        patcher = mock.patch("apis.services.storage.boto3.client")
        factory = patcher.start()
        self.addCleanup(patcher.stop)
        client = mock.Mock()
        factory.return_value = client
        client.generate_presigned_url.return_value = "https://test-bucket.example/signed"
        client.head_object.return_value = {
            "ContentLength": 1000, "ContentType": "image/jpeg",
        }
        return client

    @override_settings(**S3_TEST_SETTINGS)
    def test_file_upload_url(self):
        self._mocked_storage()
        self.assert_post_within_budget(
            "file_upload_url",
            APIClient(),
            "/api/files/upload-url",
            {"content_type": "image/jpeg", "size": 1000},
        )

    @override_settings(**S3_TEST_SETTINGS)
    def test_file_confirm(self):
        self._mocked_storage()
        self.assert_post_within_budget(
            "file_confirm",
            APIClient(),
            "/api/files/confirm",
            {"key": a_key()},
        )
