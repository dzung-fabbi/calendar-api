"""Consolidated cross-phase security suite (phase 10).

Endpoints are ENUMERATED FROM `giapha/urls.py` (via `_clan_scoped_entries()`
below), not listed from memory, so a newly added clan-scoped endpoint is
automatically part of the outsider-404 and viewer-403 matrices and a missing
one fails loudly instead of silently passing. Two groups already have
thorough dedicated coverage elsewhere and are REFERENCED, not duplicated,
per the phase-10 spec:

- cross-clan `photo_key` rejection: `test_photo_api.py::ConfirmPhotoTests::
  test_key_belonging_to_another_clan_is_rejected`
- another user's device token cannot be deleted: `test_gio_follow_api.py::
  DeviceTokenTests::test_delete_cannot_touch_another_users_token`
- the exhaustive "public surface leaks no PII" canary suite:
  `test_public_response_hardening.py`, `test_public_serializer_whitelist.py`,
  `test_public_hide_living_details.py`, `test_public_liveness_security.py`.
  `PublicSurfaceReferenceTests` below is a one-assertion smoke check tying
  that group into this matrix, not a re-implementation.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.tests.factories import bind_member, build_clan_fixture, build_person
from giapha.tests.public_helpers import PublicEndpointTestCase, enable_public_link
from giapha.urls import urlpatterns

DUMMY_ID = 999999

# Write methods that are intentionally `IsClanMember` (any role), not
# editor/owner -- excluded from the viewer-403 write matrix on purpose:
# - `clan-toi-la` (`ClanMemberBindingAPIView`): a member sets THEIR OWN
#   binding; there is no "editor of someone else's identity".
# - `clan-gio-follow-detail` (`ClanGioFollowDetailAPIView`): a member toggles
#   THEIR OWN reminder preference.
# - `clan-photo-urls` (`ClanPhotoUrlsAPIView`): POST verb, read-only intent
#   (batched presigned GET) -- see that view's docstring.
ANY_MEMBER_WRITE_NAMES = frozenset({'clan-toi-la', 'clan-gio-follow-detail', 'clan-photo-urls'})
_WRITE_METHODS = ('post', 'put', 'patch', 'delete')


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _clan_scoped_entries():
    """Every `giapha.urls` entry whose path includes `<int:clan_id>` --
    i.e. every endpoint this matrix's "outsider must get 404" rule applies
    to. Excludes `/join` and `/devices` (not clan-scoped by design) and the
    `public/...` routes (no-auth, a different threat model -- see
    `PublicSurfaceReferenceTests`).
    """
    return [entry for entry in urlpatterns if 'clan_id' in entry.pattern.converters]


def _dummy_kwargs(entry, clan_id):
    """`clan_id` set to the real target; every OTHER path parameter
    (`person_id`, `marriage_id`, ...) set to an id that cannot exist --
    correct because the permission check (which is what every test below
    probes) runs in DRF's `initial()`, before the view ever looks at those
    other ids.
    """
    return {name: (clan_id if name == 'clan_id' else DUMMY_ID) for name in entry.pattern.converters}


def _write_methods_of(entry):
    view_class = entry.callback.view_class
    return [method for method in _WRITE_METHODS if method in view_class.__dict__]


class UrlEnumerationCoverageTests(TestCase):
    """Fails loudly if `giapha/urls.py` gains/loses a clan-scoped endpoint
    without this file's expectations changing -- the whole point of
    enumerating from `urls.py` instead of a hand-maintained list.
    """

    def test_at_least_the_known_clan_scoped_endpoints_are_enumerated(self):
        names = {entry.name for entry in _clan_scoped_entries()}
        expected_minimum = {
            'clan-detail', 'clan-members', 'clan-member-detail', 'clan-invite-create',
            'clan-invite-detail', 'clan-lich-gio', 'clan-toi-la', 'clan-gio-follows',
            'clan-gio-follow-detail', 'clan-xung-ho', 'clan-tree', 'person-list-create',
            'person-detail', 'person-revisions', 'person-restore', 'person-photo-upload-url',
            'person-photo', 'clan-photo-urls', 'marriage-list-create', 'marriage-detail',
            'clan-public-link',
        }
        missing = expected_minimum - names
        self.assertFalse(missing, 'Endpoints removed from urls.py without updating this matrix: {}'.format(missing))


class OutsiderGetsNotFoundTests(TestCase):
    """Group 1: outsider -> 404 on EVERY clan-scoped endpoint, enumerated."""

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_sec_outsider')
        cls.clan = cls.fixture['clan']

    def test_outsider_gets_404_on_every_clan_scoped_endpoint(self):
        outsider = client_for(self.fixture['outsider'])
        for entry in _clan_scoped_entries():
            url = reverse(entry.name, kwargs=_dummy_kwargs(entry, self.clan.id))
            with self.subTest(endpoint=entry.name):
                response = outsider.get(url)
                self.assertEqual(404, response.status_code)


class EditorOfOtherClanCannotTouchTests(TestCase):
    """Group 3: editor of clan A cannot touch clan B -- same 404 rule as an
    outsider, since editor-of-A has no membership in B at all.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture_a = build_clan_fixture(ten_ho='Họ A', suffix='_sec_clan_a')
        cls.fixture_b = build_clan_fixture(ten_ho='Họ B', suffix='_sec_clan_b')

    def test_editor_of_clan_a_gets_404_on_every_clan_b_endpoint(self):
        editor_a = client_for(self.fixture_a['editor'])
        clan_b = self.fixture_b['clan']
        for entry in _clan_scoped_entries():
            url = reverse(entry.name, kwargs=_dummy_kwargs(entry, clan_b.id))
            with self.subTest(endpoint=entry.name):
                response = editor_a.get(url)
                self.assertEqual(404, response.status_code)


class ViewerGets403OnWriteEndpointsTests(TestCase):
    """Group 2: viewer -> 403 on every write endpoint, enumerated. Skips
    `ANY_MEMBER_WRITE_NAMES` (see module docstring)."""

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_sec_viewer_write')
        cls.clan = cls.fixture['clan']

    def test_viewer_gets_403_on_every_write_method_of_every_endpoint(self):
        viewer = client_for(self.fixture['viewer'])
        cases = 0
        for entry in _clan_scoped_entries():
            if entry.name in ANY_MEMBER_WRITE_NAMES:
                continue
            kwargs = _dummy_kwargs(entry, self.clan.id)
            for method in _write_methods_of(entry):
                cases += 1
                url = reverse(entry.name, kwargs=kwargs)
                with self.subTest(endpoint=entry.name, method=method):
                    response = getattr(viewer, method)(url, {}, format='json')
                    self.assertEqual(403, response.status_code)
        # A regression that silently emptied `_clan_scoped_entries()` (e.g. a
        # broken converter check) would otherwise pass this test vacuously.
        self.assertGreater(cases, 0, 'No write endpoints were exercised -- enumeration is broken.')


class PublicSurfaceReferenceTests(PublicEndpointTestCase):
    """Group 4 smoke check -- see module docstring for the authoritative,
    exhaustive canary suite this references rather than re-implements.
    `PublicEndpointTestCase` (not plain `TestCase`) clears the throttle
    cache in `setUp`, so an earlier public-endpoint test class in the same
    run cannot turn this request into a 429 (see its own docstring).
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_sec_public_ref')
        cls.clan = cls.fixture['clan']
        cls.living = build_person(cls.clan, ho_ten='Còn sống', que_quan='Bí mật', tieu_su='Bí mật')
        cls.slug = enable_public_link(cls.clan)

    def test_public_person_detail_never_leaks_grave_coordinates_or_bio_for_a_living_person(self):
        body = APIClient().get(
            reverse('public-person-detail', kwargs={'slug': self.slug, 'person_id': self.living.id}),
        ).json()['data']
        # `mo_phan_*` is never a KEY at all -- not on `PublicPersonSerializer`
        # for anyone, living or dead (see its docstring). `que_quan`/
        # `tieu_su` ARE declared keys (the dead branch uses them) but must
        # be null for a living person -- `services.public_person.
        # public_person_payload`'s living branch hardcodes them to `None`
        # regardless of what `self.living` actually has stored, and
        # `selectors.public`'s living-branch field list never even SELECTs
        # them from the DB (defence in depth -- see that module's docstring).
        for absent_key in ('mo_phan_lat', 'mo_phan_lng', 'mo_phan_note'):
            self.assertNotIn(absent_key, body)
        for nulled_key in ('que_quan', 'tieu_su'):
            self.assertIsNone(body[nulled_key])


# Groups 5 and 6 have no code here on purpose -- see the module docstring:
# - Group 5 (cross-clan `photo_key` rejected): `test_photo_api.py::
#   ConfirmPhotoTests::test_key_belonging_to_another_clan_is_rejected`.
# - Group 6 (another user's device token cannot be deleted): `test_gio_
#   follow_api.py::DeviceTokenTests::test_delete_cannot_touch_another_users_token`.
# An empty `TestCase` subclass here would contribute nothing that `grep
# test_security.py` doesn't already find via this comment, so none is added.
