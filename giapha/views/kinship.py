"""`GET /clans/{clan_id}/xung-ho?a=&b=` -- the Vietnamese kinship calculator.

`a` IS OPTIONAL, AND THAT IS THE POINT
--------------------------------------
Omitted, it defaults to the caller's own node via `ClanMember.person` -- the
binding written by `views/member_binding.py`. "What do I call this person?"
is the question the feature exists for, and making the client look its own
person id up first would be a second round trip for something the server
already knows. With no binding there is nothing to default to, so the answer
is a 400 telling the user to set it, never a guess.

QUERY BUDGET: 2 COMMON, 4 WORST CASE
------------------------------------
Common case: cached role check + `clan_kinship_rows`. Neither grows with clan
size, and `test_kinship_api.py` pins every count below alongside the answer
it produced -- a count alone passes vacuously on a 400.

Two optional paths cost one more each, both deliberately: omitting `a` adds
the binding lookup, and a pair with NO blood link adds the marriage lookup.
The marriage query is lazy rather than always because an in-law term is only
reachable once the blood walk has failed, so "what do I call my uncle" never
pays for it. BOTH AT ONCE IS 4 -- an unbound-parameter request about an
in-law, i.e. the ordinary request of a member who married in. That is the
ceiling; nothing here can cost 5.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.permissions import IsClanMember
from giapha.selectors.gio_follow import member_binding
from giapha.selectors.marriage import clan_spouse_pairs
from giapha.selectors.person import clan_kinship_rows
from giapha.serializers.kinship import KinshipSerializer
from giapha.services.kinship import resolve_kinship
from giapha.services.kinship_terms import REASON_NO_BLOOD

NOT_BOUND = (
    'Bạn chưa cho biết mình là ai trong cây gia phả. '
    'Hãy đặt liên kết ở /clans/{clan_id}/toi-la rồi thử lại, hoặc truyền tham số a.'
)
PERSON_NOT_IN_CLAN = 'Tham số {} phải là mã thành viên thuộc dòng họ này.'
MUST_BE_INT = 'Tham số {} phải là số nguyên.'
B_REQUIRED = 'Thiếu tham số b (người cần tra cứu cách xưng hô).'
BINDING_GONE = (
    'Người bạn đã liên kết trong cây gia phả không còn tồn tại. '
    'Hãy cập nhật liên kết ở /clans/{clan_id}/toi-la.'
)


def _int_param(request, name):
    """The query parameter as an `int`, or `None` when absent. 400 on junk --
    an unparsable id is a client bug, not "no such person".
    """
    raw = request.query_params.get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise BadRequestException(MUST_BE_INT.format(name))


class ClanKinshipAPIView(APIView):
    """`GET`, any clan member. See the module docstring for the budget."""

    permission_classes = [IsAuthenticated, IsClanMember]

    def get(self, request, clan_id):
        b_id = _int_param(request, 'b')
        if b_id is None:
            raise BadRequestException(B_REQUIRED)
        a_id = _int_param(request, 'a')
        # Remembered so a stale binding is not reported as a bad `a` the
        # caller never sent.
        a_from_binding = a_id is None
        if a_from_binding:
            a_id = self._bound_person_id(clan_id, request.user.id)

        rows = clan_kinship_rows(clan_id)
        # Membership of this row set IS the "same clan, not deleted" check --
        # the selector already filters on both, so no extra query is needed.
        present = set(row['id'] for row in rows)
        if a_id not in present:
            raise BadRequestException(
                BINDING_GONE.format(clan_id=clan_id) if a_from_binding
                else PERSON_NOT_IN_CLAN.format('a')
            )
        if b_id not in present:
            raise BadRequestException(PERSON_NOT_IN_CLAN.format('b'))

        result = resolve_kinship(rows, a_id, b_id)
        if result['a_calls_b']['reason'] == REASON_NO_BLOOD:
            # Only now is a marriage edge able to change the answer.
            result = resolve_kinship(rows, a_id, b_id, spouses=clan_spouse_pairs(clan_id))

        return Response(KinshipSerializer(result).data)

    @staticmethod
    def _bound_person_id(clan_id, user_id):
        member = member_binding(clan_id, user_id)
        if member is None or member.person_id is None:
            raise BadRequestException(NOT_BOUND.format(clan_id=clan_id))
        return member.person_id
