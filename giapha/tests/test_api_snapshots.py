"""Shape (not value) contract tests for the clan/membership/invite/join,
tree and person/marriage endpoints -- phases 1-4.

Freezes KEYS + VALUE TYPES via `shape_of()`, never exact values: rotating
slugs/tokens/timestamps still snapshot as `"str"`. Golden files are recorded
on first run (see `giapha/tests/shape.py`'s `SnapshotMixin` -- shared logic
lives in `testkit/shape.py`) and self-assert from the second run onward; they
were read by eye after being generated (see the phase-10 report).

Split from the remaining endpoints (`test_api_snapshots_gio_kinship.py`,
`test_api_snapshots_photo_public.py`) to stay under the file-size guideline,
same reasoning as `views/person.py`/`views/person_list.py` splitting.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.models import ClanInvite, Marriage, PersonRevision
from giapha.tests.factories import build_clan_fixture, build_person
from giapha.tests.shape import SnapshotMixin


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class CoreSnapshotTests(SnapshotMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_snap_core')
        cls.clan = cls.fixture['clan']
        cls.father = build_person(cls.clan, ho_ten='Cha')
        cls.mother = build_person(cls.clan, ho_ten='Mẹ', gioi_tinh='nu')
        cls.child = build_person(cls.clan, ho_ten='Con', father=cls.father, mother=cls.mother)
        cls.marriage = Marriage.objects.create(husband=cls.father, wife=cls.mother, status='dang_ket_hon')
        cls.invite = ClanInvite.objects.create(clan=cls.clan, code='SNAPTEST01', role='viewer')
        PersonRevision.objects.create(person=cls.child, actor=cls.fixture['editor'], action='create', payload_json='{}')

    # -- clans -----------------------------------------------------------
    def test_clan_list(self):
        body = client_for(self.fixture['owner']).get(reverse('clan-list-create')).json()
        self.assert_shape_matches('clan_list', body)

    def test_clan_create(self):
        response = client_for(self.fixture['owner']).post(
            reverse('clan-list-create'), {'ten_ho': 'Họ mới'}, format='json',
        )
        self.assertEqual(201, response.status_code)
        self.assert_shape_matches('clan_create', response.json())

    def test_clan_detail(self):
        body = client_for(self.fixture['owner']).get(
            reverse('clan-detail', kwargs={'clan_id': self.clan.id}),
        ).json()
        self.assert_shape_matches('clan_detail', body)

    # -- members -----------------------------------------------------------
    def test_clan_members(self):
        body = client_for(self.fixture['owner']).get(
            reverse('clan-members', kwargs={'clan_id': self.clan.id}),
        ).json()
        self.assert_shape_matches('clan_members', body)

    def test_clan_member_role_update(self):
        response = client_for(self.fixture['owner']).patch(
            reverse('clan-member-detail', kwargs={'clan_id': self.clan.id, 'user_id': self.fixture['viewer'].id}),
            {'role': 'editor'}, format='json',
        )
        self.assertEqual(200, response.status_code)
        self.assert_shape_matches('clan_member_role_update', response.json())

    # -- invites + join -----------------------------------------------------
    def test_invite_list(self):
        body = client_for(self.fixture['owner']).get(
            reverse('clan-invite-create', kwargs={'clan_id': self.clan.id}),
        ).json()
        self.assert_shape_matches('invite_list', body)

    def test_invite_create(self):
        response = client_for(self.fixture['owner']).post(
            reverse('clan-invite-create', kwargs={'clan_id': self.clan.id}), {}, format='json',
        )
        self.assertEqual(201, response.status_code)
        self.assert_shape_matches('invite_create', response.json())

    def test_join(self):
        new_user = self.fixture['outsider']
        response = client_for(new_user).post(reverse('clan-join'), {'code': self.invite.code}, format='json')
        self.assertEqual(200, response.status_code)
        self.assert_shape_matches('join', response.json())

    # -- tree ----------------------------------------------------------------
    def test_tree(self):
        body = client_for(self.fixture['viewer']).get(
            reverse('clan-tree', kwargs={'clan_id': self.clan.id}),
        ).json()
        self.assert_shape_matches('tree', body)

    # -- persons ---------------------------------------------------------
    def test_persons_list(self):
        body = client_for(self.fixture['viewer']).get(
            reverse('person-list-create', kwargs={'clan_id': self.clan.id}),
        ).json()
        self.assert_shape_matches('persons_list', body)

    def test_person_create(self):
        response = client_for(self.fixture['editor']).post(
            reverse('person-list-create', kwargs={'clan_id': self.clan.id}),
            {'ho_ten': 'Người mới', 'gioi_tinh': 'nam'}, format='json',
        )
        self.assertEqual(201, response.status_code)
        self.assert_shape_matches('person_create', response.json())

    def test_person_detail(self):
        body = client_for(self.fixture['viewer']).get(
            reverse('person-detail', kwargs={'clan_id': self.clan.id, 'person_id': self.child.id}),
        ).json()
        self.assert_shape_matches('person_detail', body)

    def test_person_revisions(self):
        body = client_for(self.fixture['editor']).get(
            reverse('person-revisions', kwargs={'clan_id': self.clan.id, 'person_id': self.child.id}),
        ).json()
        self.assert_shape_matches('person_revisions', body)

    def test_person_restore(self):
        revision = PersonRevision.objects.filter(person=self.child).latest('created_at')
        response = client_for(self.fixture['editor']).post(
            reverse(
                'person-restore',
                kwargs={'clan_id': self.clan.id, 'person_id': self.child.id, 'revision_id': revision.id},
            ),
        )
        self.assertEqual(200, response.status_code)
        self.assert_shape_matches('person_restore', response.json())

    # -- marriages ---------------------------------------------------------
    def test_marriages_list(self):
        body = client_for(self.fixture['viewer']).get(
            reverse('marriage-list-create', kwargs={'clan_id': self.clan.id}),
        ).json()
        self.assert_shape_matches('marriages_list', body)

    def test_marriage_create(self):
        husband = build_person(self.clan, ho_ten='Chồng 2')
        wife = build_person(self.clan, ho_ten='Vợ 2', gioi_tinh='nu')
        response = client_for(self.fixture['editor']).post(
            reverse('marriage-list-create', kwargs={'clan_id': self.clan.id}),
            {'husband_id': husband.id, 'wife_id': wife.id, 'status': 'dang_ket_hon'}, format='json',
        )
        self.assertEqual(201, response.status_code)
        self.assert_shape_matches('marriage_create', response.json())

    def test_marriage_update(self):
        response = client_for(self.fixture['editor']).patch(
            reverse('marriage-detail', kwargs={'clan_id': self.clan.id, 'marriage_id': self.marriage.id}),
            {'note': 'Ghi chú'}, format='json',
        )
        self.assertEqual(200, response.status_code)
        self.assert_shape_matches('marriage_update', response.json())
