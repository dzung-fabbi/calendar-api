"""Shape contract tests for lich-gio, xung-ho, toi-la, gio-follows and
devices -- phases 5-7. See `test_api_snapshots.py`'s module docstring for
the shared rationale (this file is a sibling split of the same suite, kept
under the file-size guideline).
"""

import datetime as dt

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.tests.factories import bind_member, build_clan_fixture, build_person
from giapha.tests.shape import SnapshotMixin


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class GioKinshipSnapshotTests(SnapshotMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_snap_gio')
        cls.clan = cls.fixture['clan']
        cls.grandparent = build_person(cls.clan, ho_ten='Cụ')
        cls.parent = build_person(
            cls.clan, ho_ten='Ông', father=cls.grandparent,
            death_solar=dt.date(1999, 5, 1), death_lunar_day=1, death_lunar_month=3,
        )
        cls.child = build_person(cls.clan, ho_ten='Cháu', father=cls.parent)
        bind_member(cls.clan, cls.fixture['viewer'], cls.child)

    # -- lich-gio -------------------------------------------------------------
    def test_lich_gio(self):
        body = client_for(self.fixture['viewer']).get(
            reverse('clan-lich-gio', kwargs={'clan_id': self.clan.id}), {'year': 2026},
        ).json()
        self.assert_shape_matches('lich_gio', body)

    # -- xung-ho ---------------------------------------------------------
    def test_xung_ho(self):
        body = client_for(self.fixture['viewer']).get(
            reverse('clan-xung-ho', kwargs={'clan_id': self.clan.id}), {'b': self.grandparent.id},
        ).json()
        self.assert_shape_matches('xung_ho', body)

    # -- toi-la ---------------------------------------------------------
    def test_toi_la_get(self):
        body = client_for(self.fixture['viewer']).get(
            reverse('clan-toi-la', kwargs={'clan_id': self.clan.id}),
        ).json()
        self.assert_shape_matches('toi_la_get', body)

    def test_toi_la_put(self):
        # `self.grandparent`, not `self.child` (already bound to `viewer` in
        # `setUpTestData` -- `ClanMember.person` is a `OneToOne`, a second
        # claim 400s) and not `self.parent` (deceased -- binding to a dead
        # person also 400s).
        response = client_for(self.fixture['editor']).put(
            reverse('clan-toi-la', kwargs={'clan_id': self.clan.id}),
            {'person_id': self.grandparent.id}, format='json',
        )
        self.assertEqual(200, response.status_code)
        self.assert_shape_matches('toi_la_put', response.json())

    # -- gio-follows -------------------------------------------------------
    def test_gio_follows_list(self):
        body = client_for(self.fixture['viewer']).get(
            reverse('clan-gio-follows', kwargs={'clan_id': self.clan.id}),
        ).json()
        self.assert_shape_matches('gio_follows_list', body)

    def test_gio_follow_update(self):
        response = client_for(self.fixture['viewer']).put(
            reverse(
                'clan-gio-follow-detail',
                kwargs={'clan_id': self.clan.id, 'person_id': self.parent.id},
            ),
            {'enabled': False}, format='json',
        )
        self.assertEqual(200, response.status_code)
        self.assert_shape_matches('gio_follow_update', response.json())

    # -- devices ---------------------------------------------------------
    def test_device_register(self):
        response = client_for(self.fixture['viewer']).post(
            reverse('device-token'), {'token': 'snap-test-token', 'platform': 'android'}, format='json',
        )
        self.assertEqual(201, response.status_code)
        self.assert_shape_matches('device_register', response.json())
