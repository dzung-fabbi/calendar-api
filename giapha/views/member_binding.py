"""`GET`/`PUT`/`DELETE /clans/{clan_id}/toi-la` -- "who am I in this tree?".

Split out of `views/gio_follow.py` (which consumes this binding) to keep both
files under 200 lines, same as `views/person.py` / `views/person_list.py`.

WHY THIS ENDPOINT EXISTS AT ALL
-------------------------------
`ClanMember` links a user to a họ but not to a node, so nothing in the
database can say "the ancestors of THIS user". Without a binding a member has
no direct line and receives no default giỗ reminder -- deliberately: guessing
which node a user is would send them another family's reminders. `GET`
therefore returns an explicit `null` so the client can prompt for it instead
of showing an empty screen with no explanation.
"""

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.permissions import IsClanMember
from giapha.selectors.gio_follow import member_binding, person_claimed_by_other
from giapha.selectors.person import get_person_or_none
from giapha.serializers.gio_follow import (
    MemberBindingSerializer,
    MemberBindingWriteSerializer,
)

MEMBER_NOT_FOUND = 'Không tìm thấy thành viên trong dòng họ này.'
PERSON_OTHER_CLAN = 'Người này không thuộc dòng họ này.'
PERSON_CLAIMED = 'Người này đã được thành viên khác nhận.'
PERSON_DECEASED = 'Không thể nhận mình là một người đã mất.'


def _is_deceased(person):
    """Any recorded death marker counts.

    Deliberately wider than the `lich-gio` rule (which needs day AND month):
    the question here is "may this user claim to be this node", and a person
    with only a solar death date recorded is still dead.
    """
    return bool(person.death_solar or person.death_lunar_day or person.death_lunar_month)


def binding_payload(member):
    """`None` -- not an empty dict -- when unbound, so the client decides on a
    single falsy check whether to show the "who are you?" prompt.
    """
    if member is None or member.person_id is None:
        return None
    return MemberBindingSerializer(
        {'person_id': member.person_id, 'ho_ten': member.person.ho_ten}
    ).data


class ClanMemberBindingAPIView(APIView):
    """Self-service only: the row written is always the caller's own
    `ClanMember`, never one named by the request body. An owner binding on
    someone else's behalf is a separate feature the MVP does not have.
    """

    permission_classes = [IsAuthenticated, IsClanMember]

    def get(self, request, clan_id):
        return Response({'data': binding_payload(member_binding(clan_id, request.user.id))})

    def put(self, request, clan_id):
        serializer = MemberBindingWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        person_id = serializer.validated_data['person_id']

        # Resolved through `clan_id` from the URL: this is what enforces
        # `person.clan_id == member.clan_id`, which MySQL cannot (no composite
        # FK -- see the `ClanMember` docstring). A person of another clan is
        # simply not found here, and is reported as 400 rather than 404
        # because the id came from the body, not from the path.
        person = get_person_or_none(clan_id, person_id)
        if person is None:
            raise BadRequestException(PERSON_OTHER_CLAN)
        if _is_deceased(person):
            raise BadRequestException(PERSON_DECEASED)
        if person_claimed_by_other(person_id, request.user.id):
            raise BadRequestException(PERSON_CLAIMED)

        member = member_binding(clan_id, request.user.id)
        if member is None:
            # `IsClanMember` already passed, so this is only reachable if the
            # membership row was deleted between that check and this line.
            raise NotFound(MEMBER_NOT_FOUND)

        member.person = person
        try:
            # The savepoint is not decoration: a failed statement poisons its
            # transaction, so catching the IntegrityError without one leaves
            # the connection unusable and turns the intended 400 into a 500
            # under `ATOMIC_REQUESTS` (or any transactional caller).
            with transaction.atomic():
                member.save(update_fields=['person'])
        except IntegrityError:
            # Lost the race against another member claiming the same node.
            # The OneToOne is the real guard; this keeps it a 400, not a 500.
            raise BadRequestException(PERSON_CLAIMED)

        return Response({'data': binding_payload(member)})

    def delete(self, request, clan_id):
        member = member_binding(clan_id, request.user.id)
        if member is not None and member.person_id is not None:
            member.person = None
            member.save(update_fields=['person'])
        return Response(status=status.HTTP_204_NO_CONTENT)
