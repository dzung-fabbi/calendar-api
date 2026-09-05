"""API-level tests for `GET /clans/{clan_id}/xung-ho`.

The mapping table itself is covered exhaustively by `test_kinship.py` on
`SimpleTestCase`; these tests assert the endpoint's own contract -- the
query budget, the `a`-defaults-to-your-own-binding behaviour, parameter
validation and permissions.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.models import Marriage
from giapha.tests.factories import bind_member, build_clan_fixture, build_person


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def xung_ho_url(clan_id, **query):
    url = reverse('clan-xung-ho', kwargs={'clan_id': clan_id})
    if query:
        url += '?' + '&'.join('{}={}'.format(k, v) for k, v in query.items())
    return url


class KinshipAPITestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']
        cls.owner = cls.fixture['owner']
        cls.viewer = cls.fixture['viewer']
        cls.outsider = cls.fixture['outsider']

        cls.ong = build_person(cls.clan, ho_ten='Ông nội')
        cls.bac = build_person(cls.clan, ho_ten='Bác trai', father=cls.ong, birth_order=1)
        cls.bo = build_person(cls.clan, ho_ten='Bố', father=cls.ong, birth_order=2)
        cls.chu = build_person(cls.clan, ho_ten='Chú', father=cls.ong, birth_order=3)
        cls.toi = build_person(cls.clan, ho_ten='Tôi', father=cls.bo, birth_order=1)
        cls.thim = build_person(cls.clan, ho_ten='Thím', gioi_tinh='nu')
        Marriage.objects.create(
            husband=cls.chu, wife=cls.thim, order=1, status='dang_ket_hon',
        )
        # The owner is bound to `toi`; the viewer deliberately is not.
        bind_member(cls.clan, cls.owner, cls.toi)

        # A person in a DIFFERENT clan, to prove the clan scope is enforced.
        cls.other = build_clan_fixture(ten_ho='Trần tộc', suffix='_2')
        cls.nguoi_la = build_person(cls.other['clan'], ho_ten='Người họ khác')


class PermissionTests(KinshipAPITestCase):
    def test_member_can_read(self):
        response = client_for(self.viewer).get(
            xung_ho_url(self.clan.id, a=self.toi.id, b=self.chu.id)
        )
        self.assertEqual(response.status_code, 200)

    def test_outsider_gets_404_not_403(self):
        """A 403 would confirm the clan exists -- house convention."""
        response = client_for(self.outsider).get(
            xung_ho_url(self.clan.id, a=self.toi.id, b=self.chu.id)
        )
        self.assertEqual(response.status_code, 404)

    def test_anonymous_is_rejected(self):
        response = APIClient().get(xung_ho_url(self.clan.id, a=self.toi.id, b=self.chu.id))
        self.assertIn(response.status_code, (401, 403))


class QueryBudgetTests(KinshipAPITestCase):
    """Every case asserts the ANSWER as well as the count.

    Counting alone passes vacuously: a 400 raised before the optional queries
    costs exactly the same as the success path it is meant to pin.
    """

    def test_explicit_a_and_a_blood_relation_costs_two_queries(self):
        """Cached role check + `clan_kinship_rows`, and nothing per person.
        A regression here means a query moved inside the walk.
        """
        client = client_for(self.owner)
        with self.assertNumQueries(2):
            response = client.get(xung_ho_url(self.clan.id, a=self.toi.id, b=self.chu.id))
        self.assertEqual(200, response.status_code)
        self.assertEqual('chú', response.data['a_calls_b']['term'])

    def test_defaulting_a_costs_one_more_for_the_binding(self):
        client = client_for(self.owner)
        with self.assertNumQueries(3):
            response = client.get(xung_ho_url(self.clan.id, b=self.chu.id))
        self.assertEqual(200, response.status_code)
        self.assertEqual('chú', response.data['a_calls_b']['term'])

    def test_no_blood_relation_costs_one_more_for_the_marriages(self):
        """The marriage table is loaded lazily: only a pair with no blood
        link can have their answer changed by it.
        """
        client = client_for(self.owner)
        with self.assertNumQueries(3):
            response = client.get(xung_ho_url(self.clan.id, a=self.toi.id, b=self.thim.id))
        self.assertEqual(200, response.status_code)
        self.assertEqual('thím', response.data['a_calls_b']['term'])

    def test_worst_case_is_four_queries(self):
        """The true ceiling, stated rather than left to be multiplied out:
        role + binding + rows + marriages. Both optional queries at once is
        the ordinary request of a member who married in.
        """
        client = client_for(self.owner)
        with self.assertNumQueries(4):
            response = client.get(xung_ho_url(self.clan.id, b=self.thim.id))
        self.assertEqual(200, response.status_code)
        self.assertEqual('thím', response.data['a_calls_b']['term'])


class DefaultingTests(KinshipAPITestCase):
    def test_a_defaults_to_the_callers_own_binding(self):
        response = client_for(self.owner).get(xung_ho_url(self.clan.id, b=self.chu.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual('chú', response.data['a_calls_b']['term'])
        self.assertEqual('cháu', response.data['b_calls_a']['term'])

    def test_unbound_caller_omitting_a_gets_400_telling_them_to_bind(self):
        response = client_for(self.viewer).get(xung_ho_url(self.clan.id, b=self.chu.id))
        self.assertEqual(response.status_code, 400)
        self.assertIn('toi-la', str(response.data['detail']))


class ParameterTests(KinshipAPITestCase):
    def test_b_is_required(self):
        response = client_for(self.owner).get(xung_ho_url(self.clan.id, a=self.toi.id))
        self.assertEqual(response.status_code, 400)

    def test_non_integer_id_is_400(self):
        response = client_for(self.owner).get(
            xung_ho_url(self.clan.id, a=self.toi.id, b='abc')
        )
        self.assertEqual(response.status_code, 400)

    def test_person_from_another_clan_is_400(self):
        response = client_for(self.owner).get(
            xung_ho_url(self.clan.id, a=self.toi.id, b=self.nguoi_la.id)
        )
        self.assertEqual(response.status_code, 400)

    def test_soft_deleted_person_is_400(self):
        gone = build_person(self.clan, ho_ten='Đã xoá', is_deleted=True)
        response = client_for(self.owner).get(
            xung_ho_url(self.clan.id, a=self.toi.id, b=gone.id)
        )
        self.assertEqual(response.status_code, 400)


class ResponseShapeTests(KinshipAPITestCase):
    def test_full_payload(self):
        response = client_for(self.owner).get(
            xung_ho_url(self.clan.id, a=self.toi.id, b=self.bac.id)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {'a_calls_b', 'b_calls_a', 'common_ancestor', 'path', 'explain'},
            set(response.data),
        )
        self.assertEqual('bác', response.data['a_calls_b']['term'])
        self.assertTrue(response.data['a_calls_b']['confident'])
        self.assertEqual(self.ong.id, response.data['common_ancestor']['id'])
        self.assertEqual(
            {'a_up': 2, 'b_up': 1, 'side': 'noi'}, dict(response.data['path'])
        )

    def test_in_law_resolves_through_the_marriage(self):
        response = client_for(self.owner).get(
            xung_ho_url(self.clan.id, a=self.toi.id, b=self.thim.id)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual('thím', response.data['a_calls_b']['term'])

    def test_unrelated_pair_is_200_with_a_null_term(self):
        la = build_person(self.clan, ho_ten='Người dưng')
        response = client_for(self.owner).get(
            xung_ho_url(self.clan.id, a=self.toi.id, b=la.id)
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['a_calls_b']['term'])
        self.assertEqual('khong_cung_huyet_thong', response.data['a_calls_b']['reason'])
        self.assertIsNone(response.data['common_ancestor'])

    def test_missing_birth_order_is_flagged_not_guessed(self):
        mo_ho = build_person(self.clan, ho_ten='Chưa rõ thứ bậc', father=self.ong)
        response = client_for(self.owner).get(
            xung_ho_url(self.clan.id, a=self.toi.id, b=mo_ho.id)
        )
        self.assertEqual('bác/chú', response.data['a_calls_b']['term'])
        self.assertFalse(response.data['a_calls_b']['confident'])
        # `reason` là slug máy đọc; chữ tiếng Việt cho người dùng ở `explain`.
        self.assertEqual('thieu_birth_order', response.data['a_calls_b']['reason'])
        self.assertIn('thiếu birth_order', response.data['explain'])

    def test_same_person_twice(self):
        response = client_for(self.owner).get(
            xung_ho_url(self.clan.id, a=self.toi.id, b=self.toi.id)
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['a_calls_b']['term'])
        self.assertEqual('cung_mot_nguoi', response.data['a_calls_b']['reason'])
