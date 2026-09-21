"""Regressions for the scope-escalation holes found in review (plan 260919):
re-parenting, marriage pull-in, invite ladder, branch-editor restore and
self-binding, invites surviving member removal, link-import capacity.
"""

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from giapha.models import ClanInvite, ClanMember, Person, PersonRevision
from giapha.tests.family_helpers import family_of
from giapha.tests.scope_helpers import build_scoped_clan, client_for


class ScopeEscalationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_escalate')
        cls.clan = cls.fx['clan']

    def setUp(self):
        cache.clear()

    def person_url(self, key):
        return reverse('person-detail', kwargs={'clan_id': self.clan.id, 'person_id': self.fx[key].id})

    def viewer(self):
        return client_for(self.fx['viewer'])

    def test_reparenting_own_node_under_outsider_is_forbidden(self):
        response = self.viewer().patch(self.person_url('self_node'), {'father_id': self.fx['con_bac'].id}, format='json')
        self.assertEqual(403, response.status_code)
        self.assertEqual(403, self.viewer().patch(self.person_url('con_bac'), {'nghe_nghiep': 'x'},
                                                  format='json').status_code)

    def test_new_child_needs_every_parent_in_scope(self):
        url = reverse('person-list-create', kwargs={'clan_id': self.clan.id})
        body = {'ho_ten': 'X', 'gioi_tinh': 'nam', 'father_id': self.fx['con'].id, 'mother_id': self.fx['ba'].id}
        self.assertEqual(403, self.viewer().post(url, body, format='json').status_code)

    def test_marrying_an_existing_relative_is_forbidden_but_new_spouse_ok(self):
        url = reverse('marriage-list-create', kwargs={'clan_id': self.clan.id})
        bad = {'husband_id': self.fx['con'].id, 'wife_id': self.fx['ba'].id, 'status': 'dang_ket_hon'}
        self.assertEqual(403, self.viewer().post(url, bad, format='json').status_code)
        self.assertEqual(403, self.viewer().patch(self.person_url('ba'), {'nghe_nghiep': 'x'},
                                                  format='json').status_code)
        fresh = Person.objects.create(clan=self.clan, ho_ten='Dâu mới', gioi_tinh='nu')
        ok = {'husband_id': self.fx['con'].id, 'wife_id': fresh.id, 'status': 'dang_ket_hon'}
        self.assertEqual(201, self.viewer().post(url, ok, format='json').status_code)

    def test_inviting_own_parent_or_sibling_needs_approval(self):
        url = reverse('clan-invite-create', kwargs={'clan_id': self.clan.id})
        for key in ('cha', 'em'):
            with self.subTest(person=key):
                data = self.viewer().post(url, {'person_id': self.fx[key].id}, format='json').json()['data']
                self.assertEqual('pending_approval', data['status'])
                self.assertIsNone(data['code'])
        child = self.viewer().post(url, {'person_id': self.fx['con'].id}, format='json').json()['data']
        self.assertEqual('active', child['status'])

    def test_branch_editor_cannot_restore_outside_branch(self):
        ClanMember.objects.filter(user=self.fx['editor']).update(scope_root_person=self.fx['bac'])
        revision = PersonRevision.objects.create(person=self.fx['cha'], actor=None, action='update', payload_json='{}')
        url = reverse('person-restore', kwargs={
            'clan_id': self.clan.id, 'person_id': self.fx['cha'].id, 'revision_id': revision.id})
        self.assertEqual(403, client_for(self.fx['editor']).post(url, {}, format='json').status_code)

    def test_branch_editor_self_claim_outside_branch_is_unverified(self):
        ClanMember.objects.filter(user=self.fx['editor']).update(scope_root_person=self.fx['bac'])
        url = reverse('clan-toi-la', kwargs={'clan_id': self.clan.id})
        response = client_for(self.fx['editor']).put(url, {'person_id': self.fx['em'].id}, format='json')
        self.assertFalse(response.json()['data']['person_verified'])

    def test_removed_member_invites_are_revoked(self):
        url = reverse('clan-invite-create', kwargs={'clan_id': self.clan.id})
        code = self.viewer().post(url, {'person_id': self.fx['con'].id}, format='json').json()['data']['code']
        member_url = reverse('clan-member-detail', kwargs={'clan_id': self.clan.id, 'user_id': self.fx['viewer'].id})
        self.assertEqual(204, client_for(self.fx['owner']).delete(member_url).status_code)
        self.assertFalse(ClanInvite.objects.filter(code=code).exists())

    def test_link_import_respects_family_cap(self):
        family_of(self.fx['viewer'])
        ids = [self.fx[k].id for k in ('ong', 'ba', 'cha', 'me')]
        with self.settings(FAMILY_MAX_PERSONS=3):
            response = self.viewer().post(reverse('family-link-import'),
                                          {'clanId': self.clan.id, 'clanPersonIds': ids}, format='json')
        self.assertEqual(400, response.status_code)
        self.assertEqual('FAMILY_FULL', response.json()['error']['code'])
