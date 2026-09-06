"""Regression tests for H1 (phase-9 security review): a partial death
record must never flip a living person to the public "dead" field list.

`giapha.selectors.public._is_living` used to be OR-semantics (`death_solar
is None and death_lunar_day is None and death_lunar_month is None`) -- ANY
ONE of the three columns being set flipped a person onto the DEAD branch,
publishing `ten_huy`/birth year/`que_quan`/`nghe_nghiep`/`tieu_su`/photo for
someone who is, per the data, still alive (no complete death date at all).

REST writes are guarded by `services.person_rules.
validate_death_pair_complete`, but this state is reachable through the
Django admin (`giapha.admin.person.PersonAdmin` is a plain `ModelAdmin`,
no `clean()`), a CSV import, a data migration, or a raw
`Person.objects.filter(...).update(...)` -- none of which go through that
validator. These tests build the partial record directly via
`Person.objects.create` (bypassing the serializer entirely, same as those
paths would), matching the actual threat model.
"""

from giapha.tests.factories import build_clan_fixture, build_person
from giapha.tests.public_helpers import (
    PublicEndpointTestCase, anon_client, enable_public_link, node_for, public_person_url, public_tree_url,
)

SENSITIVE_DETAIL_FIELDS = (
    'ten_huy', 'ten_tu', 'ten_hieu', 'thuy_hieu', 'birth_year', 'death_year',
    'death_lunar', 'que_quan', 'nghe_nghiep', 'tieu_su', 'photo_url',
)


class PartialDeathRecordFailsClosedTests(PublicEndpointTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_public_partial_death')
        cls.clan = cls.fixture['clan']
        cls.slug = enable_public_link(cls.clan)

        # Bypasses `validate_death_pair_complete` on purpose -- ORM create,
        # not the serializer -- to reproduce the admin/CSV-import/migration
        # threat model H1 is about.
        cls.month_only = build_person(
            cls.clan, ho_ten='Chỉ Có Tháng', birth_solar=None,
            death_solar=None, death_lunar_day=None, death_lunar_month=8,
            tieu_su='Không được lộ', photo_key='giapha/x/month/photo.jpg',
        )
        cls.day_only = build_person(
            cls.clan, ho_ten='Chỉ Có Ngày', birth_solar=None,
            death_solar=None, death_lunar_day=15, death_lunar_month=None,
            tieu_su='Không được lộ', photo_key='giapha/x/day/photo.jpg',
        )

    def test_month_only_record_is_living_on_tree_node(self):
        nodes = anon_client().get(public_tree_url(self.slug)).json()['nodes']
        node = node_for(nodes, self.month_only.id)
        self.assertTrue(node['is_living'], 'a month-only death record must read as living, not dead')
        self.assertIsNone(node['ten_huy'])
        self.assertIsNone(node['birth_year'])
        self.assertIsNone(node['death_year'])
        self.assertIsNone(node['death_lunar'])
        self.assertFalse(node['has_photo'])

    def test_day_only_record_is_living_on_tree_node(self):
        nodes = anon_client().get(public_tree_url(self.slug)).json()['nodes']
        node = node_for(nodes, self.day_only.id)
        self.assertTrue(node['is_living'], 'a day-only death record must read as living, not dead')
        self.assertIsNone(node['ten_huy'])
        self.assertIsNone(node['birth_year'])
        self.assertIsNone(node['death_year'])
        self.assertIsNone(node['death_lunar'])
        self.assertFalse(node['has_photo'])

    def test_month_only_record_is_living_on_person_detail(self):
        data = anon_client().get(public_person_url(self.slug, self.month_only.id)).json()['data']
        self.assertTrue(data['is_living'], 'a month-only death record must read as living, not dead')
        for field in SENSITIVE_DETAIL_FIELDS:
            self.assertIsNone(data[field], '{} must not be disclosed for a not-actually-dead person'.format(field))

    def test_day_only_record_is_living_on_person_detail(self):
        data = anon_client().get(public_person_url(self.slug, self.day_only.id)).json()['data']
        self.assertTrue(data['is_living'], 'a day-only death record must read as living, not dead')
        for field in SENSITIVE_DETAIL_FIELDS:
            self.assertIsNone(data[field], '{} must not be disclosed for a not-actually-dead person'.format(field))
