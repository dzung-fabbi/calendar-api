"""`GET /clans/{clan_id}/tree` -- flat nodes+edges payload for client-side
layout. The server never computes x/y coordinates: screen size and drawing
style differ per client.

Query budget is exactly 3 for any clan size: the `IsClanMember` role check
(1, cached) plus the 2 queries inside `tree_payload` (persons, marriages).
`?root=&depth=` restricts to one person's subtree and costs nothing extra --
it's filtered in memory from the same 2 queries.
"""

from django.conf import settings
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.permissions import IsClanMember
from giapha.selectors.tree import tree_payload
from giapha.serializers.tree import TreeSerializer

PERSON_NOT_FOUND = 'Không tìm thấy thành viên.'


def _parse_positive_int(request, name):
    """`None` if absent; a `BadRequestException` naming the parameter if
    present but not a positive integer.
    """
    raw = request.query_params.get(name)
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        raise BadRequestException('Tham số {} phải là số nguyên.'.format(name))
    if value <= 0:
        raise BadRequestException('Tham số {} phải là số nguyên dương.'.format(name))
    return value


class ClanTreeAPIView(APIView):
    """`GET`, any clan member. See module docstring for the query budget."""

    permission_classes = [IsAuthenticated, IsClanMember]

    def get(self, request, clan_id):
        root_id = _parse_positive_int(request, 'root')
        depth = _parse_positive_int(request, 'depth')

        payload = tree_payload(
            clan_id, max_persons=settings.MAX_CLAN_PERSONS, root_id=root_id, depth=depth,
        )
        if payload is None:
            raise NotFound(PERSON_NOT_FOUND)

        return Response(TreeSerializer(payload).data)
