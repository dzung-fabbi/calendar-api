"""Permission-matrix tests: every cell of the phase-2 matrix, the outsider
404-not-403 rule, and the ≤1-query role-cache contract.
"""

from types import SimpleNamespace

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient, APIRequestFactory

from giapha.permissions import IsClanEditor, IsClanMember, IsClanOwner
from giapha.tests.factories import build_clan_fixture


def client_for(user):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


class ClanPermissionMatrixTests(TestCase):
    """Every action x role cell from the phase-2 permission matrix."""

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']

    def detail_url(self):
        return reverse('clan-detail', kwargs={'clan_id': self.clan.id})

    def members_url(self):
        return reverse('clan-members', kwargs={'clan_id': self.clan.id})

    def member_url(self, user_id):
        return reverse('clan-member-detail', kwargs={'clan_id': self.clan.id, 'user_id': user_id})

    def invites_url(self):
        return reverse('clan-invite-create', kwargs={'clan_id': self.clan.id})

    # -- Xem cây, hồ sơ, lịch giỗ (đại diện bởi GET clan detail & members): owner/editor/viewer OK --
    def test_all_members_can_view_clan_detail(self):
        for role in ('owner', 'editor', 'viewer'):
            with self.subTest(role=role):
                response = client_for(self.fixture[role]).get(self.detail_url())
                self.assertEqual(200, response.status_code)

    def test_all_members_can_view_member_list(self):
        for role in ('owner', 'editor', 'viewer'):
            with self.subTest(role=role):
                response = client_for(self.fixture[role]).get(self.members_url())
                self.assertEqual(200, response.status_code)

    # -- Đổi visibility / xoá dòng họ: owner only --
    def test_only_owner_can_patch_clan(self):
        for role, expected in (('owner', 200), ('editor', 403), ('viewer', 403)):
            with self.subTest(role=role):
                response = client_for(self.fixture[role]).patch(
                    self.detail_url(), {'ten_ho': 'Đổi tên'}, format='json',
                )
                self.assertEqual(expected, response.status_code)

    def test_only_owner_can_delete_clan(self):
        for role, expected in (('editor', 403), ('viewer', 403)):
            with self.subTest(role=role):
                response = client_for(self.fixture[role]).delete(self.detail_url())
                self.assertEqual(expected, response.status_code)
        response = client_for(self.fixture['owner']).delete(self.detail_url())
        self.assertEqual(204, response.status_code)

    # -- Sinh mã mời / đổi vai trò / gỡ thành viên: owner only --
    def test_only_owner_can_create_invite(self):
        for role, expected in (('editor', 403), ('viewer', 403), ('owner', 201)):
            with self.subTest(role=role):
                response = client_for(self.fixture[role]).post(self.invites_url(), {}, format='json')
                self.assertEqual(expected, response.status_code)

    def test_only_owner_can_change_member_role(self):
        target = self.fixture['viewer']
        for role, expected in (('editor', 403), ('viewer', 403)):
            with self.subTest(role=role):
                response = client_for(self.fixture[role]).patch(
                    self.member_url(target.id), {'role': 'editor'}, format='json',
                )
                self.assertEqual(expected, response.status_code)
        response = client_for(self.fixture['owner']).patch(
            self.member_url(target.id), {'role': 'editor'}, format='json',
        )
        self.assertEqual(200, response.status_code)

    def test_only_owner_can_remove_member(self):
        for role, expected in (('editor', 403), ('viewer', 403)):
            with self.subTest(role=role):
                response = client_for(self.fixture[role]).delete(self.member_url(self.fixture['viewer'].id))
                self.assertEqual(expected, response.status_code)
        response = client_for(self.fixture['owner']).delete(self.member_url(self.fixture['editor'].id))
        self.assertEqual(204, response.status_code)

    # -- Outsider must get 404, never 403: existence must not leak. --
    def test_outsider_gets_404_not_403_on_every_clan_scoped_endpoint(self):
        outsider_client = client_for(self.fixture['outsider'])
        cases = [
            ('get', self.detail_url()),
            ('patch', self.detail_url()),
            ('delete', self.detail_url()),
            ('get', self.members_url()),
            ('post', self.invites_url()),
            ('patch', self.member_url(self.fixture['viewer'].id)),
            ('delete', self.member_url(self.fixture['viewer'].id)),
        ]
        for method, url in cases:
            with self.subTest(method=method, url=url):
                response = getattr(outsider_client, method)(url, {}, format='json')
                self.assertEqual(404, response.status_code)

    def test_anonymous_gets_401_not_404(self):
        """Anonymous is a distinct case from outsider -- fails auth, not membership."""
        response = client_for(None).get(self.detail_url())
        self.assertEqual(401, response.status_code)

    def test_head_and_options_use_the_read_permission_not_owner_only(self):
        """M1: HEAD/OPTIONS on the clan detail must use `IsClanMember` (any
        role), not the `IsClanOwner` write permission -- they were previously
        matched by `!= 'GET'`."""
        viewer_client = client_for(self.fixture['viewer'])
        self.assertEqual(200, viewer_client.head(self.detail_url()).status_code)
        self.assertEqual(200, viewer_client.options(self.detail_url()).status_code)

    def test_member_roster_hides_email_from_non_owners(self):
        """M8: the roster is `IsClanMember` (any role); only the owner may
        see member email addresses.
        """
        owner_data = client_for(self.fixture['owner']).get(self.members_url()).json()['data']
        self.assertTrue(all('email' in row for row in owner_data))

        for role in ('editor', 'viewer'):
            with self.subTest(role=role):
                data = client_for(self.fixture[role]).get(self.members_url()).json()['data']
                self.assertTrue(all('email' not in row for row in data))

    def test_public_slug_hidden_from_non_owners(self):
        self.clan.public_slug = 'noi-toc'
        self.clan.save(update_fields=['public_slug'])

        owner_data = client_for(self.fixture['owner']).get(self.detail_url()).json()['data']
        self.assertIn('public_slug', owner_data)
        self.assertEqual('noi-toc', owner_data['public_slug'])

        for role in ('editor', 'viewer'):
            with self.subTest(role=role):
                data = client_for(self.fixture[role]).get(self.detail_url()).json()['data']
                self.assertNotIn('public_slug', data)


class RoleCacheQueryCountTests(TestCase):
    """The role cache must make a second permission check on the same
    clan_id within a request free -- at most one query total.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()

    def test_stacked_permission_checks_cost_one_query(self):
        request = APIRequestFactory().get('/')
        request.user = self.fixture['owner']
        view = SimpleNamespace(kwargs={'clan_id': self.fixture['clan'].id})

        with self.assertNumQueries(1):
            self.assertTrue(IsClanMember().has_permission(request, view))
            self.assertTrue(IsClanEditor().has_permission(request, view))
            self.assertTrue(IsClanOwner().has_permission(request, view))
