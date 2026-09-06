"""Field-whitelist canary tests for the phase-9 public gia phả surface --
the most important deliverable of this phase (see the phase spec's risk
assessment).

Split up once this file crossed the 200-line ceiling
(`docs/code-standards.md` -> Files): 404/access-control tests live in
`test_public_access_control.py`, header/rendering hardening in
`test_public_response_hardening.py`, throttle tests in
`test_public_throttle.py`, liveness-classification (H1) tests in
`test_public_liveness_security.py`, `hide_living_details` flag behaviour in
`test_public_hide_living_details.py`, and the static/mutation whitelist
guard tests in `test_public_serializer_whitelist.py`.

Every test asserting absence of a field does so per-field, so a failure
names exactly which field leaked, rather than one blanket dict comparison
that only says "something is wrong".

CANARY APPROACH: the spec asks for either (a) adding a field to `Person` at
test time, or (b) asserting the payload's key set equals an explicit
expected set if a real migration would make (a) impractical. This suite
uses (b) -- MySQL DDL (`ALTER TABLE`) is not transactional in the way
Django's `TestCase` rollback relies on, so mutating the `Person` table
schema mid-test-run would either leak into later tests or require a second
real migration + reversal, both far riskier than the guarantee is worth.
Asserting `set(payload.keys()) == EXPECTED_KEYS` gives the identical
guarantee: ANY key not on the explicit expected set -- whether from a new
`Person` column reaching the serializer, or a serializer field added by
mistake -- fails the test immediately. `test_public_serializer_whitelist.
SerializerMutationDemonstrationTests` is the actual mutation exercise (add
a field to the serializer, confirm a test fails, revert) the spec's
Acceptance section asks for reported, not a permanent part of the suite.
"""

import datetime as dt
from decimal import Decimal

from giapha.tests.factories import build_clan_fixture, build_person
from giapha.tests.public_helpers import (
    PublicEndpointTestCase, anon_client, enable_public_link, node_for, public_person_url, public_tree_url,
)

EXPECTED_TREE_NODE_KEYS = {
    'id', 'ho_ten', 'ten_huy', 'generation', 'branch', 'is_truong', 'birth_order',
    'is_living', 'birth_year', 'death_year', 'death_lunar', 'has_photo',
}
# Edges were the hole the node/detail canaries above did not cover: the
# public edge serializer used to pass its dict straight through, so it
# published whatever the edge builder put there -- including `kind`
# (`parent_kind`), i.e. adoption/step-child status, for LIVING people.
EXPECTED_TREE_EDGE_KEYS = {'type', 'from', 'to', 'role'}
EXPECTED_PERSON_DETAIL_KEYS = {
    'id', 'ho_ten', 'ten_huy', 'ten_tu', 'ten_hieu', 'thuy_hieu',
    'generation', 'branch', 'is_truong', 'birth_order', 'is_living',
    'birth_year', 'death_year', 'death_lunar', 'que_quan', 'nghe_nghiep',
    'tieu_su', 'photo_url',
}
FORBIDDEN_KEYS = ('mo_phan_lat', 'mo_phan_lng', 'mo_phan_note', 'gioi_tinh', 'photo_key')


class PublicTreeAndDetailFieldWhitelistTests(PublicEndpointTestCase):
    """`Clan.hide_living_details` left at its default (`True`)."""

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_public_whitelist')
        cls.clan = cls.fixture['clan']
        cls.slug = enable_public_link(cls.clan)

        cls.living = build_person(
            cls.clan, ho_ten='Nguyễn Đình An', ten_huy='HuýSống', ten_tu='TựSống',
            ten_hieu='HiệuSống', thuy_hieu='ThụySống', que_quan='QuêSống',
            nghe_nghiep='NghềSống', tieu_su='TiểuSửSống', photo_key='giapha/x/1/photo.jpg',
            birth_solar=dt.date(1990, 5, 1), mo_phan_lat=Decimal('10.123456'),
            mo_phan_lng=Decimal('106.123456'), mo_phan_note='MộSống',
            generation=2, branch='Chi 1', birth_order=1, is_truong=True,
        )
        cls.dead = build_person(
            cls.clan, ho_ten='Nguyễn Đình Bảo', ten_huy='HuýMất', ten_tu='TựMất',
            ten_hieu='HiệuMất', thuy_hieu='ThụyMất', que_quan='QuêMất',
            nghe_nghiep='NghềMất', tieu_su='TiểuSửMất', photo_key='giapha/x/2/photo.jpg',
            birth_solar=dt.date(1900, 1, 1), death_solar=dt.date(1980, 6, 15),
            mo_phan_lat=Decimal('11.123456'), mo_phan_lng=Decimal('107.123456'), mo_phan_note='MộMất',
            generation=1, branch='Chi 1', birth_order=1, is_truong=True,
        )

        # Link them so the tree actually has a parent edge to assert on --
        # without a link `edges` is empty and the edge whitelist test can
        # pass vacuously. `parent_kind='nuoi'` is chosen deliberately: this
        # makes the LIVING person an adopted child, so if that status ever
        # reaches the public payload by any route the tests below fail.
        cls.living.father = cls.dead
        cls.living.parent_kind = 'nuoi'
        cls.living.save(update_fields=['father', 'parent_kind'])

    def test_living_person_forbidden_fields_absent_from_tree_node(self):
        response = anon_client().get(public_tree_url(self.slug))
        self.assertEqual(200, response.status_code)
        node = node_for(response.json()['nodes'], self.living.id)

        self.assertEqual('Nguyễn Đình A.', node['ho_ten'], 'living ho_ten must be abbreviated by default')
        self.assertIsNone(node['ten_huy'], 'ten_huy leaked for living person')
        self.assertIsNone(node['birth_year'], 'birth_year leaked for living person')
        self.assertIsNone(node['death_year'], 'death_year leaked for living person')
        self.assertIsNone(node['death_lunar'], 'death_lunar leaked for living person')
        self.assertFalse(node['has_photo'], 'has_photo must be False for living person even if a photo exists')
        for key in FORBIDDEN_KEYS:
            self.assertNotIn(key, node, '{} must never be a key in the public tree node'.format(key))

    def test_living_person_forbidden_fields_absent_from_detail(self):
        response = anon_client().get(public_person_url(self.slug, self.living.id))
        self.assertEqual(200, response.status_code)
        data = response.json()['data']

        self.assertEqual('Nguyễn Đình A.', data['ho_ten'])
        self.assertIsNone(data['ten_huy'], 'ten_huy leaked for living person')
        self.assertIsNone(data['ten_tu'], 'ten_tu leaked for living person')
        self.assertIsNone(data['ten_hieu'], 'ten_hieu leaked for living person')
        self.assertIsNone(data['thuy_hieu'], 'thuy_hieu leaked for living person')
        self.assertIsNone(data['birth_year'], 'birth_year leaked for living person')
        self.assertIsNone(data['death_year'], 'death_year leaked for living person')
        self.assertIsNone(data['death_lunar'], 'death_lunar leaked for living person')
        self.assertIsNone(data['que_quan'], 'que_quan leaked for living person')
        self.assertIsNone(data['nghe_nghiep'], 'nghe_nghiep leaked for living person')
        self.assertIsNone(data['tieu_su'], 'tieu_su leaked for living person')
        self.assertIsNone(data['photo_url'], 'photo_url leaked for living person')
        for key in FORBIDDEN_KEYS:
            self.assertNotIn(key, data, '{} must never be a key in the public person detail'.format(key))

    def test_dead_person_grave_coordinates_absent_from_tree_node(self):
        response = anon_client().get(public_tree_url(self.slug))
        node = node_for(response.json()['nodes'], self.dead.id)
        for key in ('mo_phan_lat', 'mo_phan_lng', 'mo_phan_note'):
            self.assertNotIn(key, node, 'grave coordinates must never be public, dead or alive')
        # Sanity check the OTHER direction too: a dead person's genealogical
        # fields ARE shown, so the test above is meaningfully exercising
        # the whitelist rather than an empty response.
        self.assertEqual('Nguyễn Đình Bảo', node['ho_ten'])
        self.assertEqual(1980, node['death_year'])

    def test_dead_person_grave_coordinates_absent_from_detail(self):
        response = anon_client().get(public_person_url(self.slug, self.dead.id))
        data = response.json()['data']
        for key in ('mo_phan_lat', 'mo_phan_lng', 'mo_phan_note'):
            self.assertNotIn(key, data, 'grave coordinates must never be public, dead or alive')
        self.assertEqual('TiểuSửMất', data['tieu_su'])

    def test_tree_node_key_set_is_exactly_the_whitelist(self):
        response = anon_client().get(public_tree_url(self.slug))
        nodes = response.json()['nodes']
        self.assertEqual(EXPECTED_TREE_NODE_KEYS, set(node_for(nodes, self.living.id).keys()))
        self.assertEqual(EXPECTED_TREE_NODE_KEYS, set(node_for(nodes, self.dead.id).keys()))

    def test_tree_edge_key_set_is_exactly_the_whitelist(self):
        """Guards `edges`, not just `nodes`. A passthrough edge serializer
        publishes any key the builder adds, so this is what stops a future
        field riding out on an edge instead of a node.
        """
        edges = anon_client().get(public_tree_url(self.slug)).json()['edges']
        self.assertTrue(edges, 'fixture must produce at least one parent edge')
        for edge in edges:
            self.assertEqual(EXPECTED_TREE_EDGE_KEYS, set(edge.keys()))

    def test_parent_kind_never_appears_anywhere_in_the_public_tree(self):
        """`parent_kind` (`ruot`/`nuoi`/`ke`) is not on the phase-9
        whitelist table and must not reach the public surface by any route
        -- node, edge, or key name.

        Asserted over the PARSED response (L9 fix, phase-9 review): a raw
        substring check like `assertNotIn('"kind"', body)` would false-fail
        against a legitimately-named clan/branch/person containing the text
        `kind` or `ke`/`nuoi`/`ruot` anywhere in an unrelated field (e.g. a
        branch literally named "Ke" or a `ho_ten` containing "Ruột" as part
        of an unrelated word). Checking the structured `nodes`/`edges` for
        the ABSENCE of the `kind`/`parent_kind` keys is the guarantee that
        was actually intended, without depending on what values happen to
        appear elsewhere in the fixture.
        """
        body = anon_client().get(public_tree_url(self.slug)).json()
        for node in body['nodes']:
            self.assertNotIn('kind', node)
            self.assertNotIn('parent_kind', node)
        for edge in body['edges']:
            self.assertNotIn('kind', edge)
            self.assertNotIn('parent_kind', edge)
        # `parent_kind` as a literal string (the field name itself, not a
        # value) is still safe to check on the raw body -- no legitimate
        # clan/person/branch name is expected to collide with this exact
        # identifier, unlike the bare `ke`/`nuoi`/`ruot` values above.
        raw_body = anon_client().get(public_tree_url(self.slug)).content.decode()
        self.assertNotIn('parent_kind', raw_body)

    def test_person_detail_key_set_is_exactly_the_whitelist(self):
        living_data = anon_client().get(public_person_url(self.slug, self.living.id)).json()['data']
        dead_data = anon_client().get(public_person_url(self.slug, self.dead.id)).json()['data']
        self.assertEqual(EXPECTED_PERSON_DETAIL_KEYS, set(living_data.keys()))
        self.assertEqual(EXPECTED_PERSON_DETAIL_KEYS, set(dead_data.keys()))


