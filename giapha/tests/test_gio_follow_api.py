"""API tests for `toi-la`, `gio-follows` and `devices`.

The direct-line walk itself is covered on `SimpleTestCase` in
`test_gio_follow_service.py`; these tests assert the endpoints expose it
faithfully, keep one member's data out of another's, and hold the query
budget flat.

FIXTURE TREE (all in one clan)

        cu (mất 5/2 âm)
        /             \\
    ong (mất 10/6)     bac (mất 3/3)     <- bàng hệ: NOT an ancestor of `toi`
       |
     toi (còn sống)                      <- the node `owner` claims

`owner` binds to `toi`, so their direct line is exactly {ong, cu}.
"""

from unittest import mock

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.models import ClanMember, DeviceToken, GioFollow, Person
from giapha.tests.factories import bind_member, build_clan_fixture, build_person

# The endpoint reads the caller's binding, the clan's deceased, the clan's
# edges and the caller's own overrides -- plus the cached role check. Five,
# and never one more per person followed.
GIO_FOLLOW_QUERY_BUDGET = 5


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def toi_la_url(clan_id):
    return reverse('clan-toi-la', kwargs={'clan_id': clan_id})


def follows_url(clan_id):
    return reverse('clan-gio-follows', kwargs={'clan_id': clan_id})


def follow_url(clan_id, person_id):
    return reverse('clan-gio-follow-detail', kwargs={'clan_id': clan_id, 'person_id': person_id})


def devices_url():
    return reverse('device-token')


class FollowTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture()
        cls.clan = cls.fixture['clan']
        cls.owner = cls.fixture['owner']
        cls.viewer = cls.fixture['viewer']
        cls.outsider = cls.fixture['outsider']

        cls.cu = build_person(
            cls.clan, ho_ten='Nguyễn Đình Cụ', generation=1,
            death_lunar_day=5, death_lunar_month=2,
        )
        cls.ong = build_person(
            cls.clan, ho_ten='Nguyễn Đình Ông', generation=2, father=cls.cu,
            death_lunar_day=10, death_lunar_month=6,
        )
        cls.bac = build_person(
            cls.clan, ho_ten='Nguyễn Đình Bác', generation=2, father=cls.cu,
            death_lunar_day=3, death_lunar_month=3,
        )
        cls.toi = build_person(cls.clan, ho_ten='Nguyễn Đình Tôi', generation=3, father=cls.ong)

    def items_by_person(self, user):
        response = client_for(user).get(follows_url(self.clan.id))
        self.assertEqual(response.status_code, 200)
        return response.data, dict((item['person_id'], item) for item in response.data['items'])


class BindingTests(FollowTestCase):
    def test_get_is_null_before_binding(self):
        """Explicit null, not 404: the client uses it to prompt "who are you
        in the tree?" -- without which the member gets no default reminders.
        """
        response = client_for(self.owner).get(toi_la_url(self.clan.id))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['data'])

    def test_put_then_get_round_trip(self):
        response = client_for(self.owner).put(
            toi_la_url(self.clan.id), {'person_id': self.toi.id}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['person_id'], self.toi.id)
        self.assertEqual(response.data['data']['ho_ten'], 'Nguyễn Đình Tôi')

        response = client_for(self.owner).get(toi_la_url(self.clan.id))
        self.assertEqual(response.data['data']['person_id'], self.toi.id)

    def test_delete_clears_binding_but_keeps_person(self):
        bind_member(self.clan, self.owner, self.toi)
        response = client_for(self.owner).delete(toi_la_url(self.clan.id))
        self.assertEqual(response.status_code, 204)
        self.assertIsNone(ClanMember.objects.get(clan=self.clan, user=self.owner).person_id)
        self.assertTrue(Person.objects.filter(id=self.toi.id).exists())

    def test_delete_is_idempotent(self):
        self.assertEqual(client_for(self.owner).delete(toi_la_url(self.clan.id)).status_code, 204)

    def test_person_of_another_clan_is_400(self):
        other = build_clan_fixture(ten_ho='Trần tộc', suffix='_2')
        stranger = build_person(other['clan'], ho_ten='Người họ khác')
        response = client_for(self.owner).put(
            toi_la_url(self.clan.id), {'person_id': stranger.id}, format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(ClanMember.objects.get(clan=self.clan, user=self.owner).person_id)

    def test_already_claimed_person_is_400_via_the_pre_check(self):
        """The COMMON path: `person_claimed_by_other` sees the collision and
        answers 400 before any write. Renamed -- it never reached the
        `IntegrityError` branch it used to be named after; the test below
        does.
        """
        bind_member(self.clan, self.owner, self.toi)
        response = client_for(self.viewer).put(
            toi_la_url(self.clan.id), {'person_id': self.toi.id}, format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('đã được thành viên khác nhận', str(response.data))

    def test_losing_the_race_is_400_and_leaves_the_connection_usable(self):
        """The RACE path: the pre-check passes, then the OneToOne rejects the
        write. Without `transaction.atomic()` around the save the failed
        statement poisons the transaction, and the query below this one raises
        `TransactionManagementError` instead of returning a row -- a latent
        500 the moment `ATOMIC_REQUESTS` is switched on.
        """
        bind_member(self.clan, self.owner, self.toi)
        with mock.patch(
            'giapha.views.member_binding.person_claimed_by_other', return_value=False,
        ):
            response = client_for(self.viewer).put(
                toi_la_url(self.clan.id), {'person_id': self.toi.id}, format='json',
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn('đã được thành viên khác nhận', str(response.data))
        # The assertion that actually detects the missing savepoint:
        self.assertEqual(
            ClanMember.objects.get(clan=self.clan, user=self.owner).person_id, self.toi.id,
        )
        self.assertIsNone(ClanMember.objects.get(clan=self.clan, user=self.viewer).person_id)

    def test_rebinding_to_own_person_is_allowed(self):
        """`person_claimed_by_other` excludes the caller, so a repeated PUT of
        the same value is not mistaken for a collision.
        """
        bind_member(self.clan, self.owner, self.toi)
        response = client_for(self.owner).put(
            toi_la_url(self.clan.id), {'person_id': self.toi.id}, format='json',
        )
        self.assertEqual(response.status_code, 200)

    def test_deceased_person_is_400(self):
        response = client_for(self.owner).put(
            toi_la_url(self.clan.id), {'person_id': self.ong.id}, format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_soft_deleted_person_is_400(self):
        gone = build_person(self.clan, ho_ten='Đã xoá', is_deleted=True)
        response = client_for(self.owner).put(
            toi_la_url(self.clan.id), {'person_id': gone.id}, format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_person_id_is_400(self):
        response = client_for(self.owner).put(toi_la_url(self.clan.id), {}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_leaving_the_clan_drops_the_binding_not_the_person(self):
        """`on_delete=SET_NULL` protects the other direction; this asserts the
        one that matters for privacy -- a departed member must stop being
        resolvable to a node of a clan they can no longer read.
        """
        bind_member(self.clan, self.viewer, self.toi)
        ClanMember.objects.filter(clan=self.clan, user=self.viewer).delete()

        self.assertTrue(Person.objects.filter(id=self.toi.id).exists())
        self.assertFalse(ClanMember.objects.filter(person_id=self.toi.id).exists())


class GioFollowListTests(FollowTestCase):
    def test_direct_ancestors_are_followed_by_default(self):
        bind_member(self.clan, self.owner, self.toi)
        payload, items = self.items_by_person(self.owner)

        self.assertTrue(payload['bound'])
        self.assertEqual(set(items), {self.ong.id, self.cu.id})
        for person_id in (self.ong.id, self.cu.id):
            self.assertEqual(items[person_id]['source'], 'truc-he')
            self.assertTrue(items[person_id]['followed'])
        # Bàng hệ: same clan, not on the caller's line, never a default.
        self.assertNotIn(self.bac.id, items)

    def test_row_shape(self):
        bind_member(self.clan, self.owner, self.toi)
        _payload, items = self.items_by_person(self.owner)
        row = items[self.ong.id]
        self.assertEqual(row['ho_ten'], 'Nguyễn Đình Ông')
        self.assertEqual(row['generation'], 2)
        self.assertEqual(row['lunar'], {'day': 10, 'month': 6})

    def test_truncated_is_reported_like_tree_and_lich_gio(self):
        """A clan at `MAX_CLAN_PERSONS` must say its list is cut, not drop the
        tail in silence -- a follow screen missing an ancestor also means that
        ancestor silently stops being reminded.
        """
        from django.test import override_settings

        bind_member(self.clan, self.owner, self.toi)
        payload, _items = self.items_by_person(self.owner)
        self.assertFalse(payload['truncated'])

        with override_settings(MAX_CLAN_PERSONS=2):
            response = client_for(self.owner).get(follows_url(self.clan.id))
        self.assertTrue(response.data['truncated'])

    def test_unbound_member_gets_nothing_by_default(self):
        payload, items = self.items_by_person(self.viewer)
        self.assertFalse(payload['bound'])
        self.assertEqual(items, {})

    def test_manual_add_is_thu_cong(self):
        bind_member(self.clan, self.owner, self.toi)
        response = client_for(self.owner).put(
            follow_url(self.clan.id, self.bac.id), {'enabled': True}, format='json',
        )
        self.assertEqual(response.status_code, 200)

        _payload, items = self.items_by_person(self.owner)
        self.assertEqual(items[self.bac.id]['source'], 'thu-cong')
        self.assertTrue(items[self.bac.id]['followed'])

    def test_manual_removal_is_da_bo(self):
        bind_member(self.clan, self.owner, self.toi)
        client_for(self.owner).put(
            follow_url(self.clan.id, self.ong.id), {'enabled': False}, format='json',
        )
        _payload, items = self.items_by_person(self.owner)
        # Still listed -- the client must be able to offer "restore" -- but
        # explicitly not followed.
        self.assertEqual(items[self.ong.id]['source'], 'da-bo')
        self.assertFalse(items[self.ong.id]['followed'])

    def test_delete_override_returns_to_default(self):
        """The reason `DELETE` exists: `PUT {enabled:true}` is NOT the way
        back, because "default" and "manually on" are different states.
        """
        bind_member(self.clan, self.owner, self.toi)
        client = client_for(self.owner)
        client.put(follow_url(self.clan.id, self.ong.id), {'enabled': False}, format='json')

        client.put(follow_url(self.clan.id, self.ong.id), {'enabled': True}, format='json')
        _payload, items = self.items_by_person(self.owner)
        self.assertTrue(items[self.ong.id]['followed'])

        response = client.delete(follow_url(self.clan.id, self.ong.id))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(GioFollow.objects.filter(person=self.ong, user=self.owner).exists())

        _payload, items = self.items_by_person(self.owner)
        self.assertEqual(items[self.ong.id]['source'], 'truc-he')
        self.assertTrue(items[self.ong.id]['followed'])

    def test_delete_is_idempotent(self):
        bind_member(self.clan, self.owner, self.toi)
        response = client_for(self.owner).delete(follow_url(self.clan.id, self.ong.id))
        self.assertEqual(response.status_code, 204)

    def test_delete_works_after_the_lunar_death_date_is_cleared(self):
        """An editor clearing the lunar date must not strand the row: the user
        can no longer see it in `GET`, so `DELETE` refusing it too would leave
        an override that is invisible AND undeletable. Removing an override is
        always meaningful; `PUT` still requires a real giỗ.
        """
        GioFollow.objects.create(person=self.bac, user=self.owner, enabled=True)
        Person.objects.filter(id=self.bac.id).update(
            death_lunar_day=None, death_lunar_month=None,
        )

        response = client_for(self.owner).delete(follow_url(self.clan.id, self.bac.id))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(GioFollow.objects.filter(person=self.bac, user=self.owner).exists())

    def test_overrides_are_per_user(self):
        """`follow_rows_for_user` filters on `request.user`; one member's
        manual adds must never surface on another member's list.
        """
        bind_member(self.clan, self.owner, self.toi)
        client_for(self.owner).put(
            follow_url(self.clan.id, self.bac.id), {'enabled': True}, format='json',
        )
        _payload, items = self.items_by_person(self.viewer)
        self.assertEqual(items, {})

    def test_put_on_a_living_person_is_400(self):
        response = client_for(self.owner).put(
            follow_url(self.clan.id, self.toi.id), {'enabled': True}, format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_put_without_enabled_is_400(self):
        response = client_for(self.owner).put(
            follow_url(self.clan.id, self.ong.id), {}, format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_put_on_another_clans_person_is_404(self):
        other = build_clan_fixture(ten_ho='Trần tộc', suffix='_3')
        stranger = build_person(
            other['clan'], ho_ten='Người họ khác', death_lunar_day=1, death_lunar_month=1,
        )
        response = client_for(self.owner).put(
            follow_url(self.clan.id, stranger.id), {'enabled': True}, format='json',
        )
        self.assertEqual(response.status_code, 404)


class GioFollowQueryBudgetTests(FollowTestCase):
    """Fixed query count. A regression means a query moved inside the loop."""

    def test_budget_on_a_small_tree(self):
        bind_member(self.clan, self.owner, self.toi)
        client = client_for(self.owner)
        with self.assertNumQueries(GIO_FOLLOW_QUERY_BUDGET):
            client.get(follows_url(self.clan.id))

    def test_budget_does_not_grow_with_the_follow_count(self):
        """Same request against a 30-deep line plus 20 manual overrides."""
        child = self.cu
        for i in range(30):
            parent = build_person(
                self.clan, ho_ten='Tổ {}'.format(i), generation=1,
                death_lunar_day=(i % 28) + 1, death_lunar_month=(i % 12) + 1,
            )
            child.father = parent
            child.save(update_fields=['father'])
            child = parent

        extras = [
            build_person(
                self.clan, ho_ten='Thêm {}'.format(i),
                death_lunar_day=(i % 28) + 1, death_lunar_month=(i % 12) + 1,
            )
            for i in range(20)
        ]
        bind_member(self.clan, self.owner, self.toi)
        GioFollow.objects.bulk_create(
            [GioFollow(person=person, user=self.owner, enabled=True) for person in extras]
        )

        client = client_for(self.owner)
        with self.assertNumQueries(GIO_FOLLOW_QUERY_BUDGET):
            response = client.get(follows_url(self.clan.id))
        # 30 ancestors + cu + ong + 20 manual adds.
        self.assertEqual(len(response.data['items']), 52)


class FollowPermissionTests(FollowTestCase):
    """Outsiders get 404 everywhere -- a 403 would confirm the clan exists."""

    def test_outsider_404_on_every_clan_scoped_route(self):
        client = client_for(self.outsider)
        self.assertEqual(client.get(toi_la_url(self.clan.id)).status_code, 404)
        self.assertEqual(
            client.put(toi_la_url(self.clan.id), {'person_id': self.toi.id}, format='json').status_code,
            404,
        )
        self.assertEqual(client.delete(toi_la_url(self.clan.id)).status_code, 404)
        self.assertEqual(client.get(follows_url(self.clan.id)).status_code, 404)
        self.assertEqual(
            client.put(follow_url(self.clan.id, self.ong.id), {'enabled': True}, format='json').status_code,
            404,
        )
        self.assertEqual(client.delete(follow_url(self.clan.id, self.ong.id)).status_code, 404)

    def test_anonymous_is_rejected(self):
        client = APIClient()
        self.assertIn(client.get(toi_la_url(self.clan.id)).status_code, (401, 403))
        self.assertIn(client.get(follows_url(self.clan.id)).status_code, (401, 403))


class DeviceTokenTests(FollowTestCase):
    def test_post_registers_a_device(self):
        response = client_for(self.owner).post(
            devices_url(), {'token': 'tok-a', 'platform': 'android'}, format='json',
        )
        self.assertEqual(response.status_code, 201)
        device = DeviceToken.objects.get(token='tok-a')
        self.assertEqual(device.user_id, self.owner.id)
        self.assertTrue(device.is_active)

    def test_response_never_echoes_the_token(self):
        """A token is a credential; no endpoint may return one."""
        response = client_for(self.owner).post(
            devices_url(), {'token': 'tok-secret', 'platform': 'ios'}, format='json',
        )
        self.assertNotIn('tok-secret', str(response.data))

    def test_post_is_an_upsert(self):
        client = client_for(self.owner)
        client.post(devices_url(), {'token': 'tok-b', 'platform': 'ios'}, format='json')
        response = client.post(devices_url(), {'token': 'tok-b', 'platform': 'web'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(DeviceToken.objects.filter(token='tok-b').count(), 1)
        self.assertEqual(DeviceToken.objects.get(token='tok-b').platform, 'web')

    def test_post_transfers_a_token_to_the_new_owner(self):
        """Shared handset / re-login. Leaving the row with the old account
        would push one family's giỗ to another's phone.
        """
        client_for(self.owner).post(
            devices_url(), {'token': 'tok-shared', 'platform': 'ios'}, format='json',
        )
        client_for(self.viewer).post(
            devices_url(), {'token': 'tok-shared', 'platform': 'ios'}, format='json',
        )
        self.assertEqual(DeviceToken.objects.filter(token='tok-shared').count(), 1)
        self.assertEqual(DeviceToken.objects.get(token='tok-shared').user_id, self.viewer.id)

    def test_post_revives_a_deactivated_token(self):
        DeviceToken.objects.create(
            user=self.owner, token='tok-dead', platform='ios', is_active=False,
        )
        client_for(self.owner).post(
            devices_url(), {'token': 'tok-dead', 'platform': 'ios'}, format='json',
        )
        self.assertTrue(DeviceToken.objects.get(token='tok-dead').is_active)

    def test_delete_removes_own_token(self):
        client = client_for(self.owner)
        client.post(devices_url(), {'token': 'tok-c', 'platform': 'ios'}, format='json')
        response = client.delete(devices_url(), {'token': 'tok-c'}, format='json')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(DeviceToken.objects.filter(token='tok-c').exists())

    def test_delete_cannot_touch_another_users_token(self):
        client_for(self.owner).post(
            devices_url(), {'token': 'tok-d', 'platform': 'ios'}, format='json',
        )
        response = client_for(self.viewer).delete(devices_url(), {'token': 'tok-d'}, format='json')
        # 204 regardless, so the response reveals nothing about ownership.
        self.assertEqual(response.status_code, 204)
        self.assertTrue(DeviceToken.objects.filter(token='tok-d').exists())

    def test_invalid_platform_is_400(self):
        response = client_for(self.owner).post(
            devices_url(), {'token': 'tok-e', 'platform': 'nokia'}, format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(DeviceToken.objects.filter(token='tok-e').exists())

    def test_outsider_may_register_a_device(self):
        """`/devices` is `IsAuthenticated` only -- not `IsClanMember`, which
        would read a `clan_id` this route does not have and 404 everyone.
        """
        response = client_for(self.outsider).post(
            devices_url(), {'token': 'tok-f', 'platform': 'web'}, format='json',
        )
        self.assertEqual(response.status_code, 201)

    def test_a_racing_insert_is_400_and_leaves_the_connection_usable(self):
        """Same savepoint trap as `toi-la`: a real, DB-level unique violation
        inside the view's `try` must be contained by a savepoint, or the 400
        is produced on a connection that can no longer run a query.
        """
        DeviceToken.objects.create(user=self.viewer, token='tok-race', platform='ios')

        def racing_upsert(**kwargs):
            # Stands in for a concurrent request that inserted this token
            # between our SELECT and our INSERT. The IntegrityError is genuine.
            DeviceToken.objects.create(user=self.owner, token='tok-race', platform='ios')

        with mock.patch.object(DeviceToken.objects, 'update_or_create', racing_upsert):
            response = client_for(self.owner).post(
                devices_url(), {'token': 'tok-race', 'platform': 'ios'}, format='json',
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(DeviceToken.objects.filter(token='tok-race').count(), 1)
        self.assertEqual(DeviceToken.objects.get(token='tok-race').user_id, self.viewer.id)

    def test_anonymous_is_rejected(self):
        response = APIClient().post(
            devices_url(), {'token': 'tok-g', 'platform': 'web'}, format='json',
        )
        self.assertIn(response.status_code, (401, 403))
