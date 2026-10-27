"""`DELETE /clans/{id}/members/me` -- a member leaves the clan on their own."""

from django.test import TestCase
from django.urls import resolve, reverse

from giapha.models import ChangeRequest, ClanInvite, ClanMember, FamilyPerson, FamilyPersonLink, Person
from giapha.tests.family_helpers import family_of, make_person
from giapha.tests.scope_helpers import add_member, build_scoped_clan, client_for
from giapha.views.clan_membership import OWNER_CANNOT_LEAVE, ClanMemberLeaveAPIView


def link(user, family_person, clan, clan_person):
    return FamilyPersonLink.objects.create(family=family_of(user), family_person=family_person,
                                           clan=clan, clan_person=clan_person, linked_by=user)


def proposal(clan, proposer, target, status='pending'):
    return ChangeRequest.objects.create(clan=clan, proposer=proposer, action='update_person',
                                        target_person=target, payload_json='{"ho_ten": "X"}', status=status)


class ClanLeaveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fx = build_scoped_clan('_leave')
        cls.clan = cls.fx['clan']
        cls.url = reverse('clan-member-leave', kwargs={'clan_id': cls.clan.id})

    def leave(self, user):
        return client_for(user).delete(self.url)

    def test_member_leaves_and_links_detach_with_snapshot(self):
        user = self.fx['viewer']
        f_ong = make_person(family_of(user), 'Tên cũ trên máy', 'male', phone='0901')
        link(user, f_ong, self.clan, self.fx['ong'])
        Person.objects.filter(id=self.fx['ong'].id).update(ho_ten='Ông Tổ')
        editor_person = make_person(family_of(self.fx['editor']), 'Của editor')
        link(self.fx['editor'], editor_person, self.clan, self.fx['ba'])

        response = self.leave(user)
        self.assertEqual(204, response.status_code, response.content)
        self.assertFalse(ClanMember.objects.filter(clan=self.clan, user=user).exists())
        self.assertFalse(FamilyPersonLink.objects.filter(family__user=user).exists())
        kept = FamilyPerson.objects.get(id=f_ong.id)
        self.assertEqual(('Ông Tổ', '0901'), (kept.name, kept.phone))
        self.assertTrue(FamilyPersonLink.objects.filter(family__user=self.fx['editor']).exists())

    def test_pending_proposals_are_withdrawn_and_others_untouched(self):
        user = self.fx['viewer']
        pending = proposal(self.clan, user, self.fx['ong'])
        approved = proposal(self.clan, user, self.fx['ba'], status='approved')
        someone_else = proposal(self.clan, self.fx['editor'], self.fx['ong'])

        self.assertEqual(204, self.leave(user).status_code)
        self.assertEqual('withdrawn', ChangeRequest.objects.get(id=pending.id).status)
        self.assertEqual('approved', ChangeRequest.objects.get(id=approved.id).status)
        self.assertEqual('pending', ChangeRequest.objects.get(id=someone_else.id).status)

    def test_editor_leaving_drops_the_invites_they_minted(self):
        editor = self.fx['editor']
        ClanInvite.objects.create(clan=self.clan, code='LEAVE01', role='viewer', created_by=editor)
        self.assertEqual(204, self.leave(editor).status_code)
        self.assertFalse(ClanInvite.objects.filter(clan=self.clan, created_by=editor).exists())

    def test_after_leaving_the_clan_is_invisible(self):
        user = self.fx['manager']
        self.assertEqual(204, self.leave(user).status_code)
        detail = reverse('clan-detail', kwargs={'clan_id': self.clan.id})
        self.assertEqual(404, client_for(user).get(detail).status_code)
        self.assertEqual(404, self.leave(user).status_code)

    def test_owner_cannot_leave_even_with_a_co_owner(self):
        add_member(self.clan, 'co_owner_leave', 'owner')
        response = self.leave(self.fx['owner'])
        self.assertEqual(400, response.status_code)
        self.assertEqual(OWNER_CANNOT_LEAVE, response.json()['detail'])
        self.assertTrue(ClanMember.objects.filter(clan=self.clan, user=self.fx['owner'], role='owner').exists())

    def test_outsider_gets_404_and_anonymous_401(self):
        self.assertEqual(404, self.leave(self.fx['outsider']).status_code)
        self.assertEqual(401, client_for(None).delete(self.url).status_code)

    def test_soft_deleted_clan_is_404(self):
        self.clan.is_deleted = True
        self.clan.save(update_fields=['is_deleted'])
        self.assertEqual(404, self.leave(self.fx['viewer']).status_code)

    def test_me_route_does_not_shadow_numeric_member_route(self):
        self.assertIs(ClanMemberLeaveAPIView, resolve(self.url).func.view_class)
        numeric = reverse('clan-member-detail', kwargs={'clan_id': self.clan.id, 'user_id': self.fx['viewer'].id})
        self.assertEqual('clan-member-detail', resolve(numeric).url_name)
        self.assertEqual(204, client_for(self.fx['owner']).delete(numeric).status_code)


class OwnerRemovesMemberTests(TestCase):
    def test_removed_members_pending_proposals_are_withdrawn(self):
        fx = build_scoped_clan('_remove')
        clan, viewer = fx['clan'], fx['viewer']
        pending = proposal(clan, viewer, fx['ong'])
        url = reverse('clan-member-detail', kwargs={'clan_id': clan.id, 'user_id': viewer.id})

        self.assertEqual(204, client_for(fx['owner']).delete(url).status_code)
        self.assertEqual('withdrawn', ChangeRequest.objects.get(id=pending.id).status)
