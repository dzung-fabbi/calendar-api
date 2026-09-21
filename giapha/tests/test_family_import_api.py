"""`PUT /v1/family/import` end to end (plan 260919 phase 3)."""

from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from giapha.models import FamilyPerson, FamilySpouse
from giapha.tests.family_helpers import client_for, family_of, make_person, make_user

URL = reverse('family-import')


def snapshot(size, with_cycle=False):
    """A chain of couples: each man `mN` married to `wN`, child `mN+1`."""
    persons = []
    for index in range(size // 2):
        man = {'id': 'fam_m{}'.format(index), 'name': 'Ông {}'.format(index), 'gender': 'male',
               'createdAt': 1690000000000 + index * 10, 'gioEventId': 'gio_{}'.format(index),
               'spouses': [{'id': 'fam_w{}'.format(index), 'type': 'married'}]}
        if index:
            man['fatherId'] = 'fam_m{}'.format(index - 1)
            man['motherId'] = 'fam_w{}'.format(index - 1)
        persons.append(man)
        persons.append({'id': 'fam_w{}'.format(index), 'name': 'Bà {}'.format(index), 'gender': 'female',
                        'createdAt': 1690000000000 + index * 10 + 1})
    if with_cycle:
        persons[0]['fatherId'] = 'fam_m1'
    return persons


class FamilyImportApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user('importer')
        self.client_ = client_for(self.user)

    def put(self, persons, key='key-1', self_id=None):
        return self.client_.put(URL, {'importKey': key, 'selfId': self_id, 'persons': persons}, format='json')

    def test_clean_snapshot_round_trips(self):
        response = self.put(snapshot(20), self_id='fam_m9')
        self.assertEqual(200, response.status_code, response.content)
        body = response.json()
        self.assertEqual(20, len(body['idMap']))
        self.assertEqual(body['idMap']['fam_m9'], body['selfId'])
        self.assertEqual([], body['skippedEdges'])

        tree = client_for(self.user).get(reverse('family-root')).json()
        by_id = {p['id']: p for p in tree['persons']}
        child = by_id[body['idMap']['fam_m3']]
        self.assertEqual(body['idMap']['fam_m2'], child['fatherId'])
        self.assertEqual(body['idMap']['fam_w2'], child['motherId'])
        self.assertEqual('gio_3', child['gioEventId'])
        self.assertEqual(1690000000030, child['createdAt'])
        self.assertEqual(10, FamilySpouse.objects.filter(family__user=self.user).count())

    def test_cycle_keeps_everyone_and_reports_one_edge(self):
        body = self.put(snapshot(6, with_cycle=True)).json()
        self.assertEqual(6, len(body['idMap']))
        self.assertEqual(1, len(body['skippedEdges']))
        self.assertEqual('PARENT_CYCLE', body['skippedEdges'][0]['code'])

    def test_retry_with_same_key_replays_id_map(self):
        first = self.put(snapshot(6)).json()
        second = self.put(snapshot(6)).json()
        self.assertEqual(first['idMap'], second['idMap'])
        self.assertEqual(6, FamilyPerson.objects.filter(family__user=self.user).count())

    def test_non_empty_family_with_other_key_is_409(self):
        make_person(family_of(self.user), 'Đã có')
        response = self.put(snapshot(4), key='key-2')
        self.assertEqual(409, response.status_code)
        self.assertEqual('FAMILY_NOT_EMPTY', response.json()['error']['code'])
        self.assertEqual(1, FamilyPerson.objects.filter(family__user=self.user).count())

    def test_over_capacity_is_400_and_writes_nothing(self):
        with self.settings(FAMILY_MAX_PERSONS=3):
            response = self.put(snapshot(4))
        self.assertEqual(400, response.status_code)
        self.assertFalse(FamilyPerson.objects.filter(family__user=self.user).exists())

    def test_missing_person_id_is_400(self):
        self.assertEqual(400, self.put([{'name': 'không id'}]).status_code)

    def test_throttled_after_five_per_hour(self):
        for _ in range(5):
            self.put([], key='k')
        self.assertEqual(429, self.put([], key='k').status_code)


class FamilyImportQueryCountTests(TestCase):
    def count(self, username, size):
        cache.clear()
        client = client_for(make_user(username))
        with CaptureQueriesContext(connection) as captured:
            response = client.put(URL, {'importKey': 'k', 'persons': snapshot(size)}, format='json')
        self.assertEqual(200, response.status_code)
        return len(captured.captured_queries)

    def test_query_count_does_not_grow_with_size(self):
        self.assertEqual(self.count('qc_small', 10), self.count('qc_large', 500))
