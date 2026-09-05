"""API-level tests for Marriage CRUD: order default/uniqueness and the
same-person / cross-clan guards. Pure-rule coverage for `marriage_distinct`
and `marriage_order_unique` lives in `test_person_rules.py`.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.models import Marriage
from giapha.tests.factories import build_clan_fixture, build_person


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def marriages_url(clan_id):
    return reverse('marriage-list-create', kwargs={'clan_id': clan_id})


def marriage_url(clan_id, marriage_id):
    return reverse('marriage-detail', kwargs={'clan_id': clan_id, 'marriage_id': marriage_id})


class MarriageCrudTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']
        cls.husband = build_person(cls.clan, ho_ten='Chồng', gioi_tinh='nam')
        cls.wife = build_person(cls.clan, ho_ten='Vợ', gioi_tinh='nu')

    def test_create_defaults_order_to_one_for_the_first_marriage(self):
        response = client_for(self.fixture['editor']).post(
            marriages_url(self.clan.id),
            {'husband_id': self.husband.id, 'wife_id': self.wife.id, 'status': 'dang_ket_hon'},
            format='json',
        )
        self.assertEqual(201, response.status_code)
        self.assertEqual(1, response.json()['data']['order'])

    def test_second_marriage_defaults_to_order_two(self):
        second_wife = build_person(self.clan, ho_ten='Vợ lẽ', gioi_tinh='nu')
        Marriage.objects.create(husband=self.husband, wife=self.wife, order=1, status='dang_ket_hon')

        response = client_for(self.fixture['editor']).post(
            marriages_url(self.clan.id),
            {'husband_id': self.husband.id, 'wife_id': second_wife.id, 'status': 'dang_ket_hon'},
            format='json',
        )
        self.assertEqual(201, response.status_code)
        self.assertEqual(2, response.json()['data']['order'])

    def test_duplicate_order_for_same_husband_is_rejected(self):
        second_wife = build_person(self.clan, ho_ten='Vợ lẽ', gioi_tinh='nu')
        Marriage.objects.create(husband=self.husband, wife=self.wife, order=1, status='dang_ket_hon')

        response = client_for(self.fixture['editor']).post(
            marriages_url(self.clan.id),
            {'husband_id': self.husband.id, 'wife_id': second_wife.id, 'order': 1, 'status': 'dang_ket_hon'},
            format='json',
        )
        self.assertEqual(400, response.status_code)

    def test_husband_equal_to_wife_is_rejected(self):
        response = client_for(self.fixture['editor']).post(
            marriages_url(self.clan.id),
            {'husband_id': self.husband.id, 'wife_id': self.husband.id, 'status': 'dang_ket_hon'},
            format='json',
        )
        self.assertEqual(400, response.status_code)

    def test_partner_from_another_clan_is_rejected(self):
        other = build_clan_fixture(ten_ho='Trần tộc', suffix='_marriage')
        foreign_wife = build_person(other['clan'], ho_ten='Người khác họ', gioi_tinh='nu')

        response = client_for(self.fixture['editor']).post(
            marriages_url(self.clan.id),
            {'husband_id': self.husband.id, 'wife_id': foreign_wife.id, 'status': 'dang_ket_hon'},
            format='json',
        )
        self.assertEqual(400, response.status_code)

    def test_viewer_gets_403_on_create(self):
        response = client_for(self.fixture['viewer']).post(
            marriages_url(self.clan.id),
            {'husband_id': self.husband.id, 'wife_id': self.wife.id, 'status': 'dang_ket_hon'},
            format='json',
        )
        self.assertEqual(403, response.status_code)

    def test_patch_updates_status(self):
        marriage = Marriage.objects.create(husband=self.husband, wife=self.wife, order=1, status='dang_ket_hon')
        response = client_for(self.fixture['editor']).patch(
            marriage_url(self.clan.id, marriage.id), {'status': 'goa'}, format='json',
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual('goa', response.json()['data']['status'])

    def test_delete_removes_the_marriage(self):
        marriage = Marriage.objects.create(husband=self.husband, wife=self.wife, order=1, status='dang_ket_hon')
        response = client_for(self.fixture['editor']).delete(marriage_url(self.clan.id, marriage.id))
        self.assertEqual(204, response.status_code)
        self.assertFalse(Marriage.objects.filter(id=marriage.id).exists())

    def test_duplicate_marriage_pair_is_a_400_not_a_500(self):
        """H5b: `unique_together = ('husband', 'wife')` raised a raw
        `IntegrityError` (naming the exact row ids in the log) before this
        fix -- it must surface as a 400 instead.
        """
        Marriage.objects.create(husband=self.husband, wife=self.wife, order=1, status='dang_ket_hon')
        response = client_for(self.fixture['editor']).post(
            marriages_url(self.clan.id),
            {'husband_id': self.husband.id, 'wife_id': self.wife.id, 'status': 'dang_ket_hon'},
            format='json',
        )
        self.assertEqual(400, response.status_code)
        self.assertEqual(1, Marriage.objects.filter(husband=self.husband, wife=self.wife).count())

    def test_viewer_head_and_options_are_not_403(self):
        """M1: HEAD/OPTIONS must use the read permission, not the
        owner/editor-only write permission."""
        viewer_client = client_for(self.fixture['viewer'])
        self.assertEqual(200, viewer_client.head(marriages_url(self.clan.id)).status_code)
        self.assertEqual(200, viewer_client.options(marriages_url(self.clan.id)).status_code)


class MarriageSoftDeletedPartnerTests(TestCase):
    """M4: a soft-deleted partner's marriage row (and their name) must not
    keep leaking through `/marriages` after `/tree` and `/persons` already
    stopped showing them.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_msoftdel')
        cls.clan = cls.fixture['clan']
        cls.husband = build_person(cls.clan, ho_ten='Chồng còn sống', gioi_tinh='nam')
        cls.wife = build_person(cls.clan, ho_ten='Vợ đã xoá', gioi_tinh='nu')
        cls.marriage = Marriage.objects.create(
            husband=cls.husband, wife=cls.wife, order=1, status='dang_ket_hon',
        )

    def test_marriage_disappears_from_list_once_a_partner_is_soft_deleted(self):
        self.wife.is_deleted = True
        self.wife.save(update_fields=['is_deleted'])

        response = client_for(self.fixture['viewer']).get(marriages_url(self.clan.id))
        ids = [row['id'] for row in response.json()['data']]
        self.assertNotIn(self.marriage.id, ids)

    def test_marriage_detail_404s_once_a_partner_is_soft_deleted(self):
        self.wife.is_deleted = True
        self.wife.save(update_fields=['is_deleted'])

        response = client_for(self.fixture['editor']).patch(
            marriage_url(self.clan.id, self.marriage.id), {'status': 'goa'}, format='json',
        )
        self.assertEqual(404, response.status_code)


class MarriageListTests(TestCase):
    """Coverage gap fix: GET /marriages was not tested.

    The endpoint requires IsClanMember (all roles) for READ,
    but IsClanEditor (owner/editor) for CREATE/PATCH/DELETE.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']
        cls.husband = build_person(cls.clan, ho_ten='Chồng', gioi_tinh='nam')
        cls.wife = build_person(cls.clan, ho_ten='Vợ', gioi_tinh='nu')
        cls.marriage = Marriage.objects.create(
            husband=cls.husband, wife=cls.wife, order=1, status='dang_ket_hon',
        )

    def test_viewer_can_list_marriages(self):
        response = client_for(self.fixture['viewer']).get(marriages_url(self.clan.id))
        self.assertEqual(200, response.status_code)

    def test_editor_can_list_marriages(self):
        response = client_for(self.fixture['editor']).get(marriages_url(self.clan.id))
        self.assertEqual(200, response.status_code)

    def test_owner_can_list_marriages(self):
        response = client_for(self.fixture['owner']).get(marriages_url(self.clan.id))
        self.assertEqual(200, response.status_code)

    def test_list_returns_marriage_data(self):
        response = client_for(self.fixture['viewer']).get(marriages_url(self.clan.id))
        self.assertEqual(200, response.status_code)
        marriages = response.json()['data']
        self.assertEqual(1, len(marriages))
        self.assertEqual(self.marriage.id, marriages[0]['id'])
        self.assertEqual(self.husband.id, marriages[0]['husband_id'])
        self.assertEqual(self.wife.id, marriages[0]['wife_id'])

    def test_outsider_gets_404_on_marriage_list(self):
        response = client_for(self.fixture['outsider']).get(marriages_url(self.clan.id))
        self.assertEqual(404, response.status_code)
