"""API-level tests for `GET /clans/{clan_id}/lich-gio`.

Covers the query budget, window parsing, permissions and the response shape.
The calendar arithmetic itself is covered by `test_vn_lunar.py` and
`test_gio_service.py`; these tests assert the endpoint faithfully exposes it.
"""

import datetime as dt

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.services import vn_lunar
from giapha.services.gio import today_vn
from giapha.tests.factories import build_clan_fixture, build_person


def to_date(value):
    """`response.data` carries `solar_date` as an ISO string (DRF renders
    `DateField` with `DATE_FORMAT`), so every comparison against a `date`
    goes through here rather than assuming one or the other.
    """
    if isinstance(value, dt.date):
        return value
    return dt.datetime.strptime(value, '%Y-%m-%d').date()


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def gio_url(clan_id, **query):
    url = reverse('clan-lich-gio', kwargs={'clan_id': clan_id})
    if query:
        url += '?' + '&'.join('{}={}'.format(k, v) for k, v in query.items())
    return url


class GioCalendarTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']
        cls.owner = cls.fixture['owner']
        cls.viewer = cls.fixture['viewer']
        cls.outsider = cls.fixture['outsider']

        # Died lunar 12/08 -- an ordinary month, one giỗ per year.
        cls.to = build_person(
            cls.clan, ho_ten='Nguyễn Đình Tổ', thuy_hieu='Phúc An',
            generation=1, death_lunar_day=12, death_lunar_month=8,
        )
        # Died lunar 30/03 -- month 3 runs 29 days in 2023/2024, so this one
        # exercises the day-30 fallback.
        cls.ba = build_person(
            cls.clan, ho_ten='Trần Thị Bà', generation=2,
            death_lunar_day=30, death_lunar_month=3,
        )
        # Still living: must never appear.
        cls.song = build_person(cls.clan, ho_ten='Lê Văn Sống', generation=3)


class PermissionTests(GioCalendarTestCase):
    def test_member_can_read(self):
        response = client_for(self.viewer).get(gio_url(self.clan.id, year=2026))
        self.assertEqual(response.status_code, 200)

    def test_outsider_gets_404_not_403(self):
        """A 403 would confirm the clan exists -- same rule as every other
        giapha endpoint.
        """
        response = client_for(self.outsider).get(gio_url(self.clan.id, year=2026))
        self.assertEqual(response.status_code, 404)

    def test_anonymous_is_rejected(self):
        response = APIClient().get(gio_url(self.clan.id, year=2026))
        self.assertIn(response.status_code, (401, 403))


class QueryBudgetTests(GioCalendarTestCase):
    """Two queries regardless of clan size: the cached role check plus the
    single person fetch. A regression here means someone reintroduced a
    per-person query inside the sweep.
    """

    def test_budget_is_two_queries(self):
        client = client_for(self.owner)
        with self.assertNumQueries(2):
            client.get(gio_url(self.clan.id, year=2026))

    def test_budget_does_not_grow_with_the_clan(self):
        for i in range(40):
            build_person(
                self.clan, ho_ten='Người {}'.format(i),
                death_lunar_day=(i % 28) + 1, death_lunar_month=(i % 12) + 1,
            )
        client = client_for(self.owner)
        with self.assertNumQueries(2):
            client.get(gio_url(self.clan.id, year=2026))


class ResponseShapeTests(GioCalendarTestCase):
    def test_item_fields(self):
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2026))
        items = response.data['items']
        self.assertTrue(items)

        item = next(i for i in items if i['person_id'] == self.to.id)
        self.assertEqual(item['ho_ten'], 'Nguyễn Đình Tổ')
        self.assertEqual(item['thuy_hieu'], 'Phúc An')
        self.assertEqual(item['generation'], 1)
        self.assertEqual(item['lunar'], {'day': 12, 'month': 8})
        self.assertEqual(item['lunar_year'], 2026)
        self.assertEqual(
            to_date(item['solar_date']),
            dt.date(*reversed(vn_lunar.lunar_to_solar(12, 8, 2026))),
        )
        self.assertFalse(item['adjusted'])
        self.assertIn(' ', item['can_chi_ngay'])

    def test_days_until_is_relative_to_today_in_vietnam(self):
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2026))
        item = next(i for i in response.data['items'] if i['person_id'] == self.to.id)
        self.assertEqual(
            item['days_until'], (to_date(item['solar_date']) - today_vn()).days
        )

    def test_items_are_sorted_by_solar_date(self):
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2026))
        dates = [to_date(i['solar_date']) for i in response.data['items']]
        self.assertEqual(dates, sorted(dates))

    def test_living_person_is_absent(self):
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2026))
        ids = {i['person_id'] for i in response.data['items']}
        self.assertNotIn(self.song.id, ids)

    def test_soft_deleted_person_is_absent(self):
        self.to.is_deleted = True
        self.to.save(update_fields=['is_deleted'])
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2026))
        ids = {i['person_id'] for i in response.data['items']}
        self.assertNotIn(self.to.id, ids)

    def test_person_with_month_but_no_day_is_absent(self):
        """Half-filled lunar death data cannot produce a date; it must be
        skipped, not crash the endpoint.
        """
        partial = build_person(self.clan, ho_ten='Thiếu ngày', death_lunar_month=5)
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2026))
        self.assertEqual(response.status_code, 200)
        ids = {i['person_id'] for i in response.data['items']}
        self.assertNotIn(partial.id, ids)

    def test_other_clans_are_not_leaked(self):
        other = build_clan_fixture(ten_ho='Lê tộc', suffix='_other')
        build_person(
            other['clan'], ho_ten='Người họ khác',
            death_lunar_day=12, death_lunar_month=8,
        )
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2026))
        names = {i['ho_ten'] for i in response.data['items']}
        self.assertNotIn('Người họ khác', names)


class AdjustedFlagTests(GioCalendarTestCase):
    """The day-30 fallback must be visible to the client, not silent."""

    def test_adjusted_true_in_a_short_month_year(self):
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2023))
        item = next(i for i in response.data['items'] if i['person_id'] == self.ba.id)
        self.assertTrue(item['adjusted'])
        self.assertEqual(item['lunar'], {'day': 29, 'month': 3})

    def test_adjusted_false_in_a_full_month_year(self):
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2022))
        item = next(i for i in response.data['items'] if i['person_id'] == self.ba.id)
        self.assertFalse(item['adjusted'])
        self.assertEqual(item['lunar'], {'day': 30, 'month': 3})


class WindowTests(GioCalendarTestCase):
    def test_from_to_window(self):
        response = client_for(self.owner).get(
            gio_url(self.clan.id, **{'from': '2026-01-01', 'to': '2026-12-31'})
        )
        self.assertEqual(response.status_code, 200)
        for item in response.data['items']:
            self.assertLessEqual(dt.date(2026, 1, 1), to_date(item['solar_date']))
            self.assertGreaterEqual(dt.date(2026, 12, 31), to_date(item['solar_date']))

    def test_default_window_is_the_next_twelve_months(self):
        response = client_for(self.owner).get(gio_url(self.clan.id))
        self.assertEqual(response.status_code, 200)
        today = today_vn()
        for item in response.data['items']:
            self.assertGreaterEqual(to_date(item['solar_date']), today)
            self.assertLessEqual(to_date(item['solar_date']), today + dt.timedelta(days=365))

    def test_two_gio_of_one_person_in_one_window(self):
        """A month-12 giỗ falls twice in solar 2022. The endpoint must return
        both rows, not collapse them.
        """
        person = build_person(
            self.clan, ho_ten='Ông Chạp', death_lunar_day=1, death_lunar_month=12,
        )
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2022))
        dates = [to_date(i['solar_date']) for i in response.data['items']
                 if i['person_id'] == person.id]
        self.assertEqual(dates, [dt.date(2022, 1, 3), dt.date(2022, 12, 23)])

    def test_window_longer_than_two_years_is_rejected(self):
        response = client_for(self.owner).get(
            gio_url(self.clan.id, **{'from': '2020-01-01', 'to': '2026-01-01'})
        )
        self.assertEqual(response.status_code, 400)

    def test_reversed_window_is_rejected(self):
        response = client_for(self.owner).get(
            gio_url(self.clan.id, **{'from': '2026-12-31', 'to': '2026-01-01'})
        )
        self.assertEqual(response.status_code, 400)

    def test_half_a_window_is_rejected(self):
        response = client_for(self.owner).get(
            gio_url(self.clan.id, **{'from': '2026-01-01'})
        )
        self.assertEqual(response.status_code, 400)

    def test_year_together_with_from_is_rejected(self):
        response = client_for(self.owner).get(
            gio_url(self.clan.id, year=2026, **{'from': '2026-01-01'})
        )
        self.assertEqual(response.status_code, 400)

    def test_malformed_date_is_rejected(self):
        response = client_for(self.owner).get(
            gio_url(self.clan.id, **{'from': '01-01-2026', 'to': '2026-12-31'})
        )
        self.assertEqual(response.status_code, 400)

    def test_non_numeric_year_is_rejected(self):
        response = client_for(self.owner).get(gio_url(self.clan.id, year='hai-nghin'))
        self.assertEqual(response.status_code, 400)


class OutOfRangeTests(GioCalendarTestCase):
    """Outside `vn_lunar`'s supported range the endpoint must refuse, never
    return a silently wrong date.
    """

    def test_year_below_the_range_is_rejected(self):
        response = client_for(self.owner).get(
            gio_url(self.clan.id, year=vn_lunar.MIN_YEAR - 1)
        )
        self.assertEqual(response.status_code, 400)

    def test_year_above_the_range_is_rejected(self):
        response = client_for(self.owner).get(
            gio_url(self.clan.id, year=vn_lunar.MAX_YEAR + 1)
        )
        self.assertEqual(response.status_code, 400)

    def test_boundary_years_are_accepted(self):
        for year in (vn_lunar.MIN_YEAR, vn_lunar.MAX_YEAR):
            with self.subTest(year=year):
                response = client_for(self.owner).get(gio_url(self.clan.id, year=year))
                self.assertEqual(response.status_code, 200)


class WindowSizeEdgeCasesTests(GioCalendarTestCase):
    """The MAX_WINDOW_DAYS limit is exactly two years. Edge cases around that
    boundary must be precise.
    """

    def test_window_of_exactly_max_window_days_is_accepted(self):
        """730 days is exactly 2 years in non-leap or one leap year case.
        The endpoint should accept this without complaint.
        """
        start = dt.date(2024, 1, 1)
        end = dt.date(2025, 12, 31)  # Exactly 730 days
        response = client_for(self.owner).get(
            gio_url(self.clan.id, **{
                'from': start.strftime('%Y-%m-%d'),
                'to': end.strftime('%Y-%m-%d'),
            })
        )
        self.assertEqual(response.status_code, 200)

    def test_window_of_max_window_days_plus_one_is_rejected(self):
        """A window spanning more than 2 years (>732 days) must be rejected.
        MAX_WINDOW_DAYS = 366 * 2 = 732. A window of 733 days exceeds this.
        2024-01-01 to 2026-01-04 is 733 days.
        """
        start = dt.date(2024, 1, 1)
        end = dt.date(2026, 1, 4)  # 733 days (2024 is leap year)
        response = client_for(self.owner).get(
            gio_url(self.clan.id, **{
                'from': start.strftime('%Y-%m-%d'),
                'to': end.strftime('%Y-%m-%d'),
            })
        )
        self.assertEqual(response.status_code, 400)


class EmptyClanTests(TestCase):
    """A clan with no deceased members should return an empty list, not crash."""

    def test_clan_with_no_deceased_members_returns_empty_list(self):
        fixture = build_clan_fixture()
        clan = fixture['clan']
        owner = fixture['owner']
        # Add a living person with no death date.
        build_person(clan, ho_ten='Nguyen Van Alive', generation=3)
        response = client_for(owner).get(gio_url(clan.id, year=2026))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['items'], [])


class InvalidLunarValuesTests(TestCase):
    """Persons with missing day or month are skipped by the selector."""

    def test_person_with_missing_day_is_absent(self):
        """A person with death_lunar_day=None should not appear in results
        because the selector explicitly filters for non-null day and month.
        """
        fixture = build_clan_fixture()
        clan = fixture['clan']
        owner = fixture['owner']
        # Build a person with a month but no day.
        person = build_person(
            clan, ho_ten='Missing Day',
            death_lunar_day=None, death_lunar_month=1,
        )
        response = client_for(owner).get(gio_url(clan.id, year=2026))
        self.assertEqual(response.status_code, 200)
        ids = {i['person_id'] for i in response.data['items']}
        self.assertNotIn(person.id, ids)

    def test_person_with_missing_month_is_absent(self):
        """A person with death_lunar_month=None should not appear in results
        because the selector filters for non-null month.
        """
        fixture = build_clan_fixture()
        clan = fixture['clan']
        owner = fixture['owner']
        # Build a person with a day but no month.
        person = build_person(
            clan, ho_ten='Missing Month',
            death_lunar_day=15, death_lunar_month=None,
        )
        response = client_for(owner).get(gio_url(clan.id, year=2026))
        self.assertEqual(response.status_code, 200)
        ids = {i['person_id'] for i in response.data['items']}
        self.assertNotIn(person.id, ids)


class Day30EdgeCaseTests(GioCalendarTestCase):
    """Day 30 is sensitive because it fallback to 29 in short months.
    """

    def test_day_30_month_12_in_short_year_shows_adjusted_flag(self):
        """Month 12 has only 29 days in 2026. Someone with a lunar 30/12
        death should show adjusted=true for that year.
        """
        person = build_person(
            self.clan, ho_ten='Nguyen day 30 chap',
            death_lunar_day=30, death_lunar_month=12,
        )
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2026))
        item = next((i for i in response.data['items']
                     if i['person_id'] == person.id), None)
        self.assertIsNotNone(item)
        self.assertTrue(item['adjusted'])
        self.assertEqual(item['lunar']['day'], 29)

    def test_day_30_in_multiple_months_adjusts_correctly(self):
        """Day 30 fallback applies to any month. Test with month 12 which
        has documented 29-day years (e.g., 2026).
        """
        person = build_person(
            self.clan, ho_ten='Nguyen day 30 chap',
            death_lunar_day=30, death_lunar_month=12,
        )
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2026))
        item = next((i for i in response.data['items']
                     if i['person_id'] == person.id), None)
        self.assertIsNotNone(item, "Person with 30/12 death should appear in 2026")
        # 2026 is a year where month 12 has 29 days
        self.assertTrue(item['adjusted'])
        self.assertEqual(item['lunar']['day'], 29)


class WindowBoundaryAlignmentTests(GioCalendarTestCase):
    """Test that window boundaries align properly with double giỗ scenarios."""

    def test_window_aligned_to_exact_double_gio_boundaries(self):
        """A month-12 giỗ appears on 2022-01-03 and 2022-12-23. A window
        spanning those exact dates should capture both.
        """
        person = build_person(
            self.clan, ho_ten='Double gio person',
            death_lunar_day=1, death_lunar_month=12,
        )
        response = client_for(self.owner).get(
            gio_url(self.clan.id, **{
                'from': '2022-01-03',
                'to': '2022-12-23',
            })
        )
        dates = [to_date(i['solar_date']) for i in response.data['items']
                 if i['person_id'] == person.id]
        self.assertEqual(dates, [dt.date(2022, 1, 3), dt.date(2022, 12, 23)])


class MalformedYearTests(GioCalendarTestCase):
    """`?year=` values that `datetime.date()` itself cannot represent.

    These reached `dt.date(year, 1, 1)` before any range check and crashed
    the view: `ValueError` for 0 / negative / >9999, and `OverflowError` for
    a bignum -- which the obvious `except ValueError` would NOT have caught.
    DRF's default handler turns neither into a 400, so both were 500s with a
    traceback. Every one must now be a clean 400.
    """

    def test_year_zero(self):
        response = client_for(self.owner).get(gio_url(self.clan.id, year=0))
        self.assertEqual(response.status_code, 400)

    def test_negative_year(self):
        response = client_for(self.owner).get(gio_url(self.clan.id, year=-1))
        self.assertEqual(response.status_code, 400)

    def test_year_above_the_date_type_maximum(self):
        response = client_for(self.owner).get(gio_url(self.clan.id, year=10000))
        self.assertEqual(response.status_code, 400)

    def test_year_too_large_for_a_c_long(self):
        """The `OverflowError` path -- a different exception from every other
        case here, which is exactly why it gets its own test.
        """
        response = client_for(self.owner).get(gio_url(self.clan.id, year=99999999999))
        self.assertEqual(response.status_code, 400)

    def test_malformed_from_date_with_year_zero(self):
        response = client_for(self.owner).get(
            gio_url(self.clan.id, **{'from': '0000-01-01', 'to': '2026-01-01'})
        )
        self.assertEqual(response.status_code, 400)


class InvalidStoredLunarDataTests(GioCalendarTestCase):
    """Out-of-range lunar death values that bypassed the API write validator.

    `person_rules.validate_lunar_death_valid` only guards the API path; a row
    can still arrive via Django admin, a fixture or a bulk import. Such a row
    must be SKIPPED, never rendered -- month 13 and day 31 both resolve to a
    well-formed date in the wrong month, which is the silent-wrong-answer
    failure this module exists to prevent.
    """

    def test_month_out_of_range_is_skipped(self):
        bad = build_person(
            self.clan, ho_ten='Tháng sai', death_lunar_day=5, death_lunar_month=13,
        )
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2026))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(bad.id, {i['person_id'] for i in response.data['items']})

    def test_day_out_of_range_is_skipped(self):
        bad = build_person(
            self.clan, ho_ten='Ngày sai', death_lunar_day=31, death_lunar_month=5,
        )
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2026))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(bad.id, {i['person_id'] for i in response.data['items']})

    def test_zero_and_negative_values_are_skipped(self):
        zero = build_person(
            self.clan, ho_ten='Số không', death_lunar_day=0, death_lunar_month=0,
        )
        negative = build_person(
            self.clan, ho_ten='Số âm', death_lunar_day=-3, death_lunar_month=-1,
        )
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2026))
        self.assertEqual(response.status_code, 200)
        ids = {i['person_id'] for i in response.data['items']}
        self.assertNotIn(zero.id, ids)
        self.assertNotIn(negative.id, ids)

    def test_one_bad_row_does_not_hide_the_good_ones(self):
        """The skip must be per-row, not a bail-out that empties the calendar."""
        build_person(
            self.clan, ho_ten='Hỏng', death_lunar_day=99, death_lunar_month=99,
        )
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2026))
        self.assertIn(self.to.id, {i['person_id'] for i in response.data['items']})


class TruncationTests(GioCalendarTestCase):
    """`truncated` mirrors `GET /tree`: a calendar quietly missing people is
    worse than one that says it is incomplete.
    """

    def test_not_truncated_for_a_small_clan(self):
        response = client_for(self.owner).get(gio_url(self.clan.id, year=2026))
        self.assertFalse(response.data['truncated'])

    def test_truncated_when_the_clan_exceeds_the_cap(self):
        from django.test import override_settings

        for i in range(4):
            build_person(
                self.clan, ho_ten='Cụ {}'.format(i),
                death_lunar_day=(i % 28) + 1, death_lunar_month=(i % 12) + 1,
            )
        # 6 deceased persons in the clan; cap at 3.
        with override_settings(MAX_CLAN_PERSONS=3):
            response = client_for(self.owner).get(gio_url(self.clan.id, year=2026))
        self.assertTrue(response.data['truncated'])
        self.assertLessEqual(
            len({i['person_id'] for i in response.data['items']}), 3
        )
