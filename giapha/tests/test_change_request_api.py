"""Change requests: propose, list/visibility, withdraw, approve/reject,
stale guard (plan 260919 phase 2).
"""

from unittest import mock

from django.test import TestCase
from django.urls import reverse

from giapha.models import ChangeRequest, Person, PersonRevision
from giapha.tests.scope_helpers import add_member, build_scoped_clan, client_for


class ChangeRequestFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_cr')
        cls.clan = cls.fx['clan']

    def list_url(self):
        return reverse('change-request-list-create', kwargs={'clan_id': self.clan.id})

    def url(self, cr_id, action=None):
        name = 'change-request-' + (action or 'detail')
        return reverse(name, kwargs={'clan_id': self.clan.id, 'cr_id': cr_id})

    def propose(self, user=None, **body):
        body.setdefault('action', 'update_person')
        body.setdefault('target_person_id', self.fx['ong'].id)
        body.setdefault('payload', {'death_lunar_day': 20, 'death_lunar_month': 12})
        return client_for(user or self.fx['viewer']).post(self.list_url(), body, format='json')

    @mock.patch('giapha.views.change_request.push_to_users')
    def test_viewer_proposal_approved_by_editor_applies_with_revision(self, push):
        response = self.propose(note='Theo sổ họ')
        self.assertEqual(201, response.status_code)
        cr_id = response.json()['data']['id']
        self.assertIn(self.fx['editor'].id, push.call_args[0][0])

        approved = client_for(self.fx['editor']).post(self.url(cr_id, 'approve'), {}, format='json')
        self.assertEqual(200, approved.status_code)
        self.fx['ong'].refresh_from_db()
        self.assertEqual((20, 12), (self.fx['ong'].death_lunar_day, self.fx['ong'].death_lunar_month))
        revision = PersonRevision.objects.filter(person=self.fx['ong']).latest('id')
        self.assertEqual(self.fx['editor'], revision.actor)
        self.assertEqual(cr_id, revision.change_request_id)
        self.assertEqual('approved', ChangeRequest.objects.get(id=cr_id).status)

    def test_invalid_payload_is_rejected_at_creation(self):
        response = self.propose(payload={'death_lunar_day': 13, 'death_lunar_month': 13, 'birth_solar': 'x'})
        self.assertEqual(400, response.status_code)
        self.assertFalse(ChangeRequest.objects.exists())

    def test_empty_payload_is_rejected(self):
        self.assertEqual(400, self.propose(payload={}).status_code)

    def test_target_edited_after_proposal_is_409_stale_unless_override(self):
        cr_id = self.propose().json()['data']['id']
        client_for(self.fx['editor']).patch(
            reverse('person-detail', kwargs={'clan_id': self.clan.id, 'person_id': self.fx['ong'].id}),
            {'nghe_nghiep': 'Thầy đồ'}, format='json',
        )
        ChangeRequest.objects.filter(id=cr_id).update(base_updated_at=self.fx['ong'].created_at)
        editor = client_for(self.fx['editor'])
        conflict = editor.post(self.url(cr_id, 'approve'), {}, format='json')
        self.assertEqual(409, conflict.status_code)
        self.assertEqual('stale', conflict.json()['code'])
        self.assertIn('current', conflict.json())
        self.assertEqual(200, editor.post(self.url(cr_id, 'approve'), {'override_stale': True}, format='json').status_code)

    def test_outsider_cannot_see_or_create(self):
        outsider = client_for(self.fx['outsider'])
        self.assertEqual(404, outsider.get(self.list_url()).status_code)
        self.assertEqual(404, self.propose(user=self.fx['outsider']).status_code)

    def test_member_sees_only_own_and_others_are_404(self):
        cr_id = self.propose().json()['data']['id']
        other = add_member(self.clan, 'other_viewer_cr', 'viewer')
        self.assertEqual([], client_for(other).get(self.list_url()).json()['data'])
        self.assertEqual(404, client_for(other).get(self.url(cr_id)).status_code)
        detail = client_for(self.fx['viewer']).get(self.url(cr_id)).json()['data']
        self.assertEqual('Ông', detail['current']['ho_ten'])

    def test_editor_lists_all_and_mine_filter(self):
        self.propose()
        editor = client_for(self.fx['editor'])
        self.assertEqual(1, len(editor.get(self.list_url(), {'status': 'pending'}).json()['data']))
        self.assertEqual(0, len(editor.get(self.list_url(), {'mine': '1'}).json()['data']))

    def test_viewer_cannot_approve(self):
        cr_id = self.propose().json()['data']['id']
        self.assertEqual(403, client_for(self.fx['viewer']).post(self.url(cr_id, 'approve'), {}, format='json').status_code)

    @mock.patch('giapha.views.change_request_review.push_to_users')
    def test_reject_requires_note_and_pushes_proposer(self, push):
        cr_id = self.propose().json()['data']['id']
        editor = client_for(self.fx['editor'])
        self.assertEqual(400, editor.post(self.url(cr_id, 'reject'), {}, format='json').status_code)
        self.assertEqual(200, editor.post(self.url(cr_id, 'reject'), {'note': 'Sai nguồn'}, format='json').status_code)
        self.assertEqual([self.fx['viewer'].id], push.call_args[0][0])
        self.assertEqual(400, editor.post(self.url(cr_id, 'approve'), {}, format='json').status_code)

    def test_withdraw_only_by_proposer_while_pending(self):
        cr_id = self.propose().json()['data']['id']
        self.assertEqual(404, client_for(self.fx['outsider']).delete(self.url(cr_id)).status_code)
        self.assertEqual(403, client_for(self.fx['editor']).delete(self.url(cr_id)).status_code)
        self.assertEqual(204, client_for(self.fx['viewer']).delete(self.url(cr_id)).status_code)
        self.assertEqual('withdrawn', ChangeRequest.objects.get(id=cr_id).status)

    def test_pending_cap_per_proposer(self):
        for _ in range(20):
            self.assertEqual(201, self.propose().status_code)
        self.assertEqual(400, self.propose().status_code)

    def test_create_person_proposal_applies(self):
        body = {'action': 'create_person', 'target_person_id': None,
                'payload': {'ho_ten': 'Con bác út', 'gioi_tinh': 'nam', 'father_id': self.fx['bac'].id}}
        cr_id = self.propose(**body).json()['data']['id']
        data = client_for(self.fx['owner']).post(self.url(cr_id, 'approve'), {}, format='json').json()['data']
        created = Person.objects.get(id=data['result_id'])
        self.assertEqual(self.fx['bac'].id, created.father_id)

    def test_delete_person_proposal_keeps_children_rule(self):
        cr_id = self.propose(action='delete_person', target_person_id=self.fx['bac'].id, payload={}).json()['data']['id']
        response = client_for(self.fx['editor']).post(self.url(cr_id, 'approve'), {}, format='json')
        self.assertEqual(400, response.status_code)
        self.assertEqual('pending', ChangeRequest.objects.get(id=cr_id).status)
        self.assertFalse(Person.objects.get(id=self.fx['bac'].id).is_deleted)

    def test_deleted_target_marks_stale(self):
        grandchild = Person.objects.create(clan=self.clan, ho_ten='Lẻ', gioi_tinh='nam')
        cr_id = self.propose(target_person_id=grandchild.id).json()['data']['id']
        Person.objects.filter(id=grandchild.id).update(is_deleted=True)
        response = client_for(self.fx['editor']).post(self.url(cr_id, 'approve'), {}, format='json')
        self.assertEqual(409, response.status_code)
        self.assertEqual('stale', ChangeRequest.objects.get(id=cr_id).status)
