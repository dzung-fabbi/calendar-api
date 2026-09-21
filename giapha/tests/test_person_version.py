"""`Person.version`: +1 on every write path, optional check on PATCH, and
change requests keyed on `base_version` (plan 260919 phase 5)."""

from unittest import mock

from django.test import TestCase
from django.urls import reverse

from giapha.models import ChangeRequest, Person, PersonRevision
from giapha.tests.scope_helpers import build_scoped_clan, client_for


class PersonVersionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_version')
        cls.clan = cls.fx['clan']

    def url(self, person, name='person-detail', **extra):
        return reverse(name, kwargs=dict({'clan_id': self.clan.id, 'person_id': person.id}, **extra))

    def version_of(self, person):
        return Person.objects.get(id=person.id).version

    def test_patch_bumps_and_exposes_version(self):
        editor = client_for(self.fx['editor'])
        self.assertEqual(1, editor.get(self.url(self.fx['ong'])).json()['data']['version'])
        body = editor.patch(self.url(self.fx['ong']), {'nghe_nghiep': 'x'}, format='json').json()['data']
        self.assertEqual(2, body['version'])

    def test_same_version_twice_second_is_409(self):
        editor = client_for(self.fx['editor'])
        first = editor.patch(self.url(self.fx['ong']), {'nghe_nghiep': 'a', 'version': 1}, format='json')
        second = client_for(self.fx['owner']).patch(
            self.url(self.fx['ong']), {'nghe_nghiep': 'b', 'version': 1}, format='json')
        self.assertEqual(200, first.status_code)
        self.assertEqual(409, second.status_code)
        self.assertEqual('VERSION_CONFLICT', second.json()['code'])
        self.assertEqual('a', second.json()['current']['nghe_nghiep'])

    def test_patch_without_version_still_works(self):
        Person.objects.filter(id=self.fx['ong'].id).update(version=7)
        response = client_for(self.fx['editor']).patch(self.url(self.fx['ong']), {'nghe_nghiep': 'x'}, format='json')
        self.assertEqual(200, response.status_code)
        self.assertEqual(8, self.version_of(self.fx['ong']))

    def test_bad_version_is_400(self):
        response = client_for(self.fx['editor']).patch(self.url(self.fx['ong']), {'version': 'x'}, format='json')
        self.assertEqual(400, response.status_code)

    def test_delete_and_restore_bump(self):
        leaf = Person.objects.create(clan=self.clan, ho_ten='Lá', gioi_tinh='nam')
        editor = client_for(self.fx['editor'])
        editor.patch(self.url(leaf), {'nghe_nghiep': 'x'}, format='json')
        revision = PersonRevision.objects.filter(person=leaf).latest('id')
        editor.post(self.url(leaf, 'person-restore', revision_id=revision.id), {}, format='json')
        self.assertEqual(3, self.version_of(leaf))
        editor.delete(self.url(leaf))
        self.assertEqual(4, self.version_of(leaf))

    @mock.patch('giapha.views.photo.storage.head',
                return_value={'content_length': 10, 'content_type': 'image/jpeg'})
    @mock.patch('giapha.views.photo.storage.delete')
    @mock.patch('giapha.views.photo.storage.is_configured', return_value=True)
    def test_photo_confirm_and_delete_bump(self, *_mocks):
        person = self.fx['ong']
        key = 'giapha/{}/{}/{}.jpg'.format(self.clan.id, person.id, 'a' * 32)
        editor = client_for(self.fx['editor'])
        self.assertEqual(200, editor.post(self.url(person, 'person-photo'), {'key': key}, format='json').status_code)
        self.assertEqual(2, self.version_of(person))
        editor.delete(self.url(person, 'person-photo'))
        self.assertEqual(3, self.version_of(person))

    def test_approved_change_request_bumps_and_uses_base_version(self):
        list_url = reverse('change-request-list-create', kwargs={'clan_id': self.clan.id})
        cr = client_for(self.fx['viewer']).post(list_url, {
            'action': 'update_person', 'target_person_id': self.fx['ong'].id, 'payload': {'nghe_nghiep': 'Đồ nho'},
        }, format='json').json()['data']
        self.assertEqual(1, cr['base_version'])
        approve = reverse('change-request-approve', kwargs={'clan_id': self.clan.id, 'cr_id': cr['id']})
        self.assertEqual(200, client_for(self.fx['editor']).post(approve, {}, format='json').status_code)
        self.assertEqual(2, self.version_of(self.fx['ong']))

    def test_change_request_is_stale_after_any_bump(self):
        list_url = reverse('change-request-list-create', kwargs={'clan_id': self.clan.id})
        cr_id = client_for(self.fx['viewer']).post(list_url, {
            'action': 'update_person', 'target_person_id': self.fx['ong'].id, 'payload': {'nghe_nghiep': 'y'},
        }, format='json').json()['data']['id']
        client_for(self.fx['editor']).patch(self.url(self.fx['ong']), {'que_quan': 'Nam Định'}, format='json')
        approve = reverse('change-request-approve', kwargs={'clan_id': self.clan.id, 'cr_id': cr_id})
        self.assertEqual(409, client_for(self.fx['editor']).post(approve, {}, format='json').status_code)
        self.assertEqual('pending', ChangeRequest.objects.get(id=cr_id).status)
