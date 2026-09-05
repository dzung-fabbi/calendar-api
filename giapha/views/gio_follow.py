"""`GET /clans/{clan_id}/gio-follows` and `PUT`/`DELETE .../{person_id}` --
whose giỗ the caller gets reminded about.

The binding these read (`ClanMember.person`) is written by
`views/member_binding.py`.

RESOLUTION, NOT A STORED LIST
-----------------------------
`GET` answers a question no single table holds. The default set is the
caller's direct-line ancestors, walked in memory from `clan_edges_all`;
`GioFollow` stores only the deviations. Every row is therefore labelled with
the `source` that put it there, so a client can explain to the user why an
ancestor is (or is no longer) on their list.

Listed rows are exactly the people the answer is *about*: the caller's
ancestors plus everyone they have said something explicit about. Including
the rest of the clan's deceased would turn a preferences screen into a second
lịch giỗ.

QUERY BUDGET: 5, FIXED
----------------------
cached role check + binding + deceased persons + edges + this caller's own
overrides. Not one of them grows with the number of people followed;
`test_gio_follow_api.py` pins it with `assertNumQueries`. A regression there
means a query moved inside the row loop.
"""

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.models import GioFollow
from giapha.permissions import IsClanMember
from giapha.selectors.gio import deceased_with_lunar_death
from giapha.selectors.gio_follow import follow_rows_for_user, member_binding
from giapha.selectors.person import clan_edges_all, get_person_or_none
from giapha.serializers.gio_follow import GioFollowListSerializer, GioFollowWriteSerializer
from giapha.services.gio_follow import ancestors, followers_by_person

PERSON_NOT_FOUND = 'Không tìm thấy thành viên trong dòng họ này.'
NOT_A_GIO_PERSON = 'Chỉ theo dõi được giỗ của người đã mất có đủ ngày và tháng âm lịch.'


def _source_for(in_line, override):
    """`da-bo` wins over `truc-he`: an explicit "no" is the reason the row is
    listed at all, and the client must offer "restore" rather than "remove".
    A redundant `enabled=True` on an ancestor stays `truc-he` -- lineage is
    the truthful explanation there.
    """
    if override is False:
        return 'da-bo'
    return 'truc-he' if in_line else 'thu-cong'


class ClanGioFollowListAPIView(APIView):
    """`GET` -- the resolved follow list for the calling member."""

    permission_classes = [IsAuthenticated, IsClanMember]

    def get(self, request, clan_id):
        user_id = request.user.id
        member = member_binding(clan_id, user_id)
        self_person_id = member.person_id if member else None

        rows, truncated = deceased_with_lunar_death(
            clan_id, max_persons=settings.MAX_CLAN_PERSONS,
        )
        # `clan_edges_all` for the same reason the reminder command uses it:
        # a soft-deleted ancestor must not sever the line above them. The
        # listed rows still come from `deceased_with_lunar_death`, so a
        # soft-deleted person is never shown. Still one query.
        edges = clan_edges_all(clan_id)
        overrides = follow_rows_for_user(clan_id, user_id)

        person_ids = set(row['id'] for row in rows)
        # An unbound member has no direct line at all -- an empty `bindings`
        # is what makes `followers_by_person` return only their manual adds.
        bindings = {user_id: self_person_id} if self_person_id else {}
        followers = followers_by_person(
            edges, bindings,
            dict(((user_id, pid), enabled) for pid, enabled in overrides.items()),
            person_ids,
        )
        line = ancestors(edges, self_person_id) if self_person_id else set()

        return Response(GioFollowListSerializer({
            'items': self._items(rows, line, overrides, followers, user_id),
            'bound': self_person_id is not None,
            'truncated': truncated,
        }).data)

    @staticmethod
    def _items(rows, line, overrides, followers, user_id):
        items = []
        for row in rows:
            person_id = row['id']
            in_line = person_id in line
            override = overrides.get(person_id)
            if not in_line and override is None:
                continue
            items.append({
                'person_id': person_id,
                'ho_ten': row['ho_ten'],
                'thuy_hieu': row['thuy_hieu'],
                'generation': row['generation'],
                'lunar': {
                    'day': row['death_lunar_day'],
                    'month': row['death_lunar_month'],
                },
                # `followers` omits people nobody follows, hence the default.
                'followed': user_id in followers.get(person_id, ()),
                'source': _source_for(in_line, override),
            })
        return items


class ClanGioFollowDetailAPIView(APIView):
    """`PUT {enabled: bool}` upserts an override; `DELETE` removes it.

    Both are needed because there are three states, not two: without `DELETE`
    a user who switched an ancestor off could never get back to "whatever the
    tree says" -- only to a manual "on" that no longer tracks the tree.
    """

    permission_classes = [IsAuthenticated, IsClanMember]

    def put(self, request, clan_id, person_id):
        person = self._gio_person_or_reject(clan_id, person_id)

        serializer = GioFollowWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        enabled = serializer.validated_data['enabled']

        GioFollow.objects.update_or_create(
            person=person, user=request.user, defaults={'enabled': enabled},
        )
        return Response({'data': {'person_id': person.id, 'enabled': enabled}})

    def delete(self, request, clan_id, person_id):
        # NO giỗ CHECK HERE, unlike `put`. If an editor later clears a
        # person's lunar death date, the user's existing row must still be
        # removable -- "stop overriding this" is always a meaningful request,
        # and requiring a giỗ would leave them with a row they can neither
        # see nor delete.
        person = self._person_or_404(clan_id, person_id)
        # Idempotent: "back to default" is already true when no row exists.
        GioFollow.objects.filter(person=person, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _person_or_404(clan_id, person_id):
        """404 for a person outside this clan -- the id came from the path."""
        person = get_person_or_none(clan_id, person_id)
        if person is None:
            raise NotFound(PERSON_NOT_FOUND)
        return person

    @classmethod
    def _gio_person_or_reject(cls, clan_id, person_id):
        """404 for a person outside this clan (the id is in the path), 400 for
        one who has no giỗ to follow (the request is well-addressed but
        meaningless).
        """
        person = cls._person_or_404(clan_id, person_id)
        if person.death_lunar_day is None or person.death_lunar_month is None:
            # A living person has no giỗ, and a death date missing its day or
            # month cannot produce one -- an override on either would be a row
            # that silently never does anything.
            raise BadRequestException(NOT_A_GIO_PERSON)
        return person
