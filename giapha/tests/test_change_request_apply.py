"""Marriage proposals through the shared write path + the daily
`expire_change_requests` job (plan 260919 phase 2).
"""

import datetime
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from giapha.models import ChangeRequest, Marriage, Person
from giapha.tests.scope_helpers import build_scoped_clan, client_for


class MarriageProposalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_cr_marriage')
        cls.clan = cls.fx['clan']

    def propose_and_approve(self, body):
        list_url = reverse('change-request-list-create', kwargs={'clan_id': self.clan.id})
        created = client_for(self.fx['viewer']).post(list_url, body, format='json')
        self.assertEqual(201, created.status_code, created.content)
        url = reverse('change-request-approve', kwargs={'clan_id': self.clan.id, 'cr_id': created.json()['data']['id']})
        return client_for(self.fx['manager']).post(url, {}, format='json')

    def test_create_update_delete_marriage(self):
        wife = Person.objects.create(clan=self.clan, ho_ten='Vợ bác', gioi_tinh='nu')
        response = self.propose_and_approve({
            'action': 'create_marriage',
            'payload': {'husband_id': self.fx['bac'].id, 'wife_id': wife.id, 'status': 'dang_ket_hon'},
        })
        self.assertEqual(200, response.status_code)
        marriage = Marriage.objects.get(husband=self.fx['bac'], wife=wife)

        self.propose_and_approve({'action': 'update_marriage', 'target_marriage_id': marriage.id,
                                  'payload': {'note': 'Theo gia phả cũ'}})
        marriage.refresh_from_db()
        self.assertEqual('Theo gia phả cũ', marriage.note)

        self.propose_and_approve({'action': 'delete_marriage', 'target_marriage_id': marriage.id})
        self.assertFalse(Marriage.objects.filter(id=marriage.id).exists())

    def test_duplicate_marriage_approval_is_400_and_stays_pending(self):
        response = self.propose_and_approve({
            'action': 'create_marriage',
            'payload': {'husband_id': self.fx['ong'].id, 'wife_id': self.fx['ba'].id, 'status': 'dang_ket_hon'},
        })
        self.assertEqual(400, response.status_code)
        self.assertEqual('pending', ChangeRequest.objects.get().status)


class ExpireChangeRequestsCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_cr_expire')
        cls.clan = cls.fx['clan']

    def make(self, days_old):
        cr = ChangeRequest.objects.create(
            clan=self.clan, proposer=self.fx['viewer'], action='update_person',
            target_person=self.fx['ong'], payload_json='{"nghe_nghiep": "x"}',
        )
        ChangeRequest.objects.filter(id=cr.id).update(created_at=timezone.now() - datetime.timedelta(days=days_old))
        return cr

    @mock.patch('giapha.management.commands.expire_change_requests.push_to_users')
    def test_expire_and_remind_once(self, push):
        old, week, fresh = self.make(31), self.make(8), self.make(1)
        call_command('expire_change_requests', stdout=StringIO())

        self.assertEqual('expired', ChangeRequest.objects.get(id=old.id).status)
        self.assertEqual('pending', ChangeRequest.objects.get(id=week.id).status)
        self.assertIsNotNone(ChangeRequest.objects.get(id=week.id).reminded_at)
        self.assertIsNone(ChangeRequest.objects.get(id=fresh.id).reminded_at)
        self.assertEqual(2, push.call_count)  # proposer (expired) + reviewers (reminder)

        push.reset_mock()
        call_command('expire_change_requests', stdout=StringIO())
        push.assert_not_called()
