"""Shared fixture for the family-scope / invite / change-request suites.

`build_scoped_clan(suffix)` = `build_clan_fixture` + a `manager` user + a
small three-generation tree where the viewer is bound to `self_node`:

    ong ── ba
    ├── bac ── (cousin: con_bac)
    └── cha ── me
        ├── self_node (viewer) ── vo
        │   └── con
        └── em
"""

from django.contrib.auth.models import User
from rest_framework.test import APIClient

from giapha.models import ClanMember, Marriage
from giapha.tests.factories import build_clan_fixture, build_person


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def add_member(clan, username, role, person=None, verified=False):
    user = User.objects.create_user(username=username, password='pw')
    ClanMember.objects.create(clan=clan, user=user, role=role, person=person, person_verified=verified)
    return user


def build_scoped_clan(suffix='', verified=True):
    fx = build_clan_fixture(suffix=suffix)
    clan = fx['clan']
    fx['manager'] = add_member(clan, 'clan_manager' + suffix, 'manager')

    ong = build_person(clan, ho_ten='Ông')
    ba = build_person(clan, ho_ten='Bà', gioi_tinh='nu')
    bac = build_person(clan, ho_ten='Bác', father=ong, mother=ba)
    con_bac = build_person(clan, ho_ten='Con bác', father=bac)
    cha = build_person(clan, ho_ten='Cha', father=ong, mother=ba)
    me = build_person(clan, ho_ten='Mẹ', gioi_tinh='nu')
    self_node = build_person(clan, ho_ten='Tôi', father=cha, mother=me)
    vo = build_person(clan, ho_ten='Vợ', gioi_tinh='nu')
    con = build_person(clan, ho_ten='Con', father=self_node, mother=vo)
    em = build_person(clan, ho_ten='Em', father=cha, mother=me)
    Marriage.objects.create(husband=ong, wife=ba, status='dang_ket_hon')
    Marriage.objects.create(husband=cha, wife=me, status='dang_ket_hon')
    Marriage.objects.create(husband=self_node, wife=vo, status='dang_ket_hon')

    ClanMember.objects.filter(clan=clan, user=fx['viewer']).update(person=self_node, person_verified=verified)
    fx.update({
        'ong': ong, 'ba': ba, 'bac': bac, 'con_bac': con_bac, 'cha': cha, 'me': me,
        'self_node': self_node, 'vo': vo, 'con': con, 'em': em,
    })
    return fx
