"""`Clan.hide_living_details` behaviour for the phase-9 public surface --
split out of `test_public_security.py` once that file crossed the 200-line
ceiling.
"""

import datetime as dt

from giapha.tests.factories import build_clan_fixture, build_person
from giapha.tests.public_helpers import (
    PublicEndpointTestCase, anon_client, enable_public_link, node_for, public_person_url, public_tree_url,
)


class HideLivingDetailsFlagTests(PublicEndpointTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_public_hide_flag')
        cls.clan = cls.fixture['clan']
        cls.slug = enable_public_link(cls.clan)
        cls.living = build_person(
            cls.clan, ho_ten='Trần Thị Bích Hương', birth_solar=dt.date(1995, 2, 2),
            tieu_su='Bí mật', photo_key='giapha/x/3/photo.jpg',
        )

    def test_default_true_abbreviates_name(self):
        response = anon_client().get(public_tree_url(self.slug))
        node = node_for(response.json()['nodes'], self.living.id)
        self.assertEqual('Trần Thị Bích H.', node['ho_ten'])

    def test_false_shows_full_name_but_still_no_dates_or_bio(self):
        self.clan.hide_living_details = False
        self.clan.save(update_fields=['hide_living_details'])

        tree_node = node_for(anon_client().get(public_tree_url(self.slug)).json()['nodes'], self.living.id)
        self.assertEqual('Trần Thị Bích Hương', tree_node['ho_ten'])
        self.assertIsNone(tree_node['birth_year'])
        self.assertFalse(tree_node['has_photo'])

        detail = anon_client().get(public_person_url(self.slug, self.living.id)).json()['data']
        self.assertEqual('Trần Thị Bích Hương', detail['ho_ten'])
        self.assertIsNone(detail['birth_year'])
        self.assertIsNone(detail['tieu_su'])
        self.assertIsNone(detail['photo_url'])
