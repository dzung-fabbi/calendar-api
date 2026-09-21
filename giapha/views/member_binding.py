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
from giapha.notifications import push_to_users
from giapha.permissions import IsClanMember, cached_member
from giapha.permissions_scope import binding_auto_verified
from giapha.selectors.clan import approver_user_ids, branch_editor_rows
from giapha.selectors.scope import scope_graph
from giapha.services.family_scope import branch_scope_ids
from giapha.selectors.gio_follow import member_binding, person_claimed_by_other
from giapha.selectors.person import get_person_or_none
from giapha.services.person_status import is_deceased
from giapha.serializers.gio_follow import (
    MemberBindingSerializer,
    MemberBindingWriteSerializer,
)

MEMBER_NOT_FOUND = 'Không tìm thấy thành viên trong dòng họ này.'
PERSON_OTHER_CLAN = 'Người này không thuộc dòng họ này.'
PERSON_CLAIMED = 'Người này đã được thành viên khác nhận.'
PERSON_DECEASED = 'Không thể nhận mình là một người đã mất.'


def _is_deceased(person):
    """`da_mat` or any recorded death marker (`services.person_status`).

    Deliberately wider than the `lich-gio` rule (which needs day AND month):
    the question here is "may this user claim to be this node", and a person
    with only a solar death date recorded is still dead.
    """
    return is_deceased(person)


def binding_payload(member):
    """`None` -- not an empty dict -- when unbound, so the client decides on a
    single falsy check whether to show the "who are you?" prompt.
    """
    if member is None or member.person_id is None:
        return None
    return MemberBindingSerializer({
        'person_id': member.person_id,
        'ho_ten': member.person.ho_ten,
        'person_verified': member.person_verified,
    }).data


def binding_reviewer_ids(clan_id, person_id):
    """Owner + managers + branch editors whose branch holds `person_id`."""
    ids = list(approver_user_ids(clan_id))
    branch_editors = branch_editor_rows(clan_id)
    if branch_editors:
        edges, marriages, _verified = scope_graph(clan_id)
        ids += [user_id for user_id, root_id in branch_editors
                if person_id in branch_scope_ids(edges, marriages, root_id)]
    return ids


def notify_claim_needs_review(clan_id, person, actor):
    """A self-claim waits for an approver -- tell the owner and managers."""
    push_to_users(
        [user_id for user_id in binding_reviewer_ids(clan_id, person.id) if user_id != actor.id],
        'Cần xác minh thành viên',
        '{} tự nhận là "{}" trong gia phả, cần xác minh.'.format(actor.get_full_name() or actor.username, person.ho_ten),
        {'type': 'binding_pending', 'clan_id': clan_id, 'user_id': actor.id, 'person_id': person.id},
    )


class ClanMemberBindingAPIView(APIView):
    """Self-service only: the row written is always the caller's own
    `ClanMember`, never one named by the request body. An owner binding on
    someone else's behalf is a separate feature the MVP does not have.

    Verification: a claim by editor+ is verified on write; a viewer's claim
    is not (`person_verified=False`) and grants no write access until an
    approver calls `members/{user_id}/verify` (`views/member_verify.py`).
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

        same_node = member.person_id == person.id
        auto_verified = binding_auto_verified(cached_member(request, clan_id), clan_id, person.id)
        member.person = person
        member.person_verified = auto_verified or (same_node and member.person_verified)
        try:
            # The savepoint is not decoration: a failed statement poisons its
            # transaction, so catching the IntegrityError without one leaves
            # the connection unusable and turns the intended 400 into a 500
            # under `ATOMIC_REQUESTS` (or any transactional caller).
            with transaction.atomic():
                member.save(update_fields=['person', 'person_verified'])
        except IntegrityError:
            # Lost the race against another member claiming the same node.
            # The OneToOne is the real guard; this keeps it a 400, not a 500.
            raise BadRequestException(PERSON_CLAIMED)

        if not member.person_verified and not same_node:
            notify_claim_needs_review(clan_id, person, request.user)
        return Response({'data': binding_payload(member)})

    def delete(self, request, clan_id):
        member = member_binding(clan_id, request.user.id)
        if member is not None and member.person_id is not None:
            member.person = None
            member.person_verified = False
            member.save(update_fields=['person', 'person_verified'])
        return Response(status=status.HTTP_204_NO_CONTENT)
