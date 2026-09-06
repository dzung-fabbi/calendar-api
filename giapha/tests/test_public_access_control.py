"""404/visibility rules for the phase-9 public gia phả surface -- split out
of `test_public_security.py` once that file crossed the 200-line ceiling.

Every scenario here must answer 404, NEVER 403 or any status that would
hint the clan/person exists -- same house rule as `permissions.py`.
"""

from django.test import override_settings

from giapha.services.public_slug import generate_public_slug
from giapha.tests.factories import build_clan_fixture, build_person
from giapha.tests.public_helpers import (
    PublicEndpointTestCase, anon_client, enable_public_link, public_person_url, public_tree_url,
)


class UnreachableSlugTests(PublicEndpointTestCase):
    """Unknown / revoked / private / soft-deleted -- all 404, never 403 or
    any status that would hint the clan exists.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_public_404')
        cls.clan = cls.fixture['clan']
        cls.person = build_person(cls.clan, ho_ten='Ai đó')

    def test_unknown_slug_is_404(self):
        response = anon_client().get(public_tree_url('this-slug-was-never-issued'))
        self.assertEqual(404, response.status_code)

    def test_private_clan_slug_is_404(self):
        # `public_slug` set but `visibility` never flipped to 'public_link'
        # -- the state a clan is in before the owner ever enables sharing.
        self.clan.public_slug = generate_public_slug()
        self.clan.save(update_fields=['public_slug'])
        response = anon_client().get(public_tree_url(self.clan.public_slug))
        self.assertEqual(404, response.status_code)

    def test_revoked_slug_is_404(self):
        slug = enable_public_link(self.clan)
        self.clan.public_slug = None
        self.clan.visibility = 'private'
        self.clan.save(update_fields=['public_slug', 'visibility'])
        response = anon_client().get(public_tree_url(slug))
        self.assertEqual(404, response.status_code)

    def test_soft_deleted_clan_is_404_even_with_a_live_looking_slug(self):
        slug = enable_public_link(self.clan)
        self.clan.is_deleted = True
        self.clan.save(update_fields=['is_deleted'])
        response = anon_client().get(public_tree_url(slug))
        self.assertEqual(404, response.status_code)

    def test_unknown_person_id_on_a_valid_slug_is_404(self):
        slug = enable_public_link(self.clan)
        response = anon_client().get(public_person_url(slug, 999999))
        self.assertEqual(404, response.status_code)

    def test_uppercased_slug_is_404(self):
        """Security fix (phase-9 review L1): MySQL's `utf8_unicode_ci`
        collation makes `WHERE public_slug = slug` case-INSENSITIVE, so an
        upper-cased mangling of a valid slug used to resolve the same clan
        -- quietly undermining `services.public_slug`'s entropy claim
        (~2^115 bits reduced to whatever a case-folded guess can hit) and
        letting a case-mangled copy of a revoked-and-reissued link still
        work. `selectors.clan.get_clan_by_public_slug` now re-checks the
        match case-sensitively in Python after the DB query.
        """
        slug = enable_public_link(self.clan)
        response = anon_client().get(public_tree_url(slug.upper()))
        self.assertEqual(404, response.status_code)
        # Sanity check: the real slug, unmodified, still resolves -- so the
        # test above is exercising case-sensitivity, not a broken fixture.
        self.assertEqual(200, anon_client().get(public_tree_url(slug)).status_code)


class CrossClanAndSoftDeletePersonTests(PublicEndpointTestCase):
    """L8: coverage for already-correct behaviour that had no assertions.

    A public slug scopes every person lookup to ITS OWN clan
    (`selectors.public.public_person_row(clan.id, person_id)` always
    filters by `clan_id`) -- a person id that resolves in a different clan,
    or that is soft-deleted, must 404 exactly like an unknown id, and must
    be entirely absent from `/tree`, not merely un-fetchable by id.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture_a = build_clan_fixture(suffix='_public_cross_a')
        cls.fixture_b = build_clan_fixture(suffix='_public_cross_b')
        cls.clan_a = cls.fixture_a['clan']
        cls.clan_b = cls.fixture_b['clan']
        cls.slug_a = enable_public_link(cls.clan_a)
        enable_public_link(cls.clan_b)

        cls.person_in_a = build_person(cls.clan_a, ho_ten='Người dòng họ A')
        cls.person_in_b = build_person(cls.clan_b, ho_ten='Người dòng họ B')
        cls.soft_deleted_in_a = build_person(cls.clan_a, ho_ten='Người đã xoá', is_deleted=True)

    def test_person_from_another_clan_is_404(self):
        response = anon_client().get(public_person_url(self.slug_a, self.person_in_b.id))
        self.assertEqual(404, response.status_code)

    def test_soft_deleted_person_is_404(self):
        response = anon_client().get(public_person_url(self.slug_a, self.soft_deleted_in_a.id))
        self.assertEqual(404, response.status_code)

    def test_soft_deleted_and_foreign_persons_absent_from_tree(self):
        nodes = anon_client().get(public_tree_url(self.slug_a)).json()['nodes']
        ids = {node['id'] for node in nodes}
        self.assertIn(self.person_in_a.id, ids)
        self.assertNotIn(self.person_in_b.id, ids, 'a person from a different clan must never appear')
        self.assertNotIn(self.soft_deleted_in_a.id, ids, 'a soft-deleted person must never appear')


class TreeTruncationTests(PublicEndpointTestCase):
    @override_settings(MAX_CLAN_PERSONS=3)
    def test_truncated_flag_set_when_clan_exceeds_the_cap(self):
        fixture = build_clan_fixture(suffix='_public_truncation')
        clan = fixture['clan']
        slug = enable_public_link(clan)
        for i in range(4):
            build_person(clan, ho_ten='Người {}'.format(i))

        body = anon_client().get(public_tree_url(slug)).json()
        self.assertTrue(body['truncated'])
        self.assertEqual(3, len(body['nodes']))
