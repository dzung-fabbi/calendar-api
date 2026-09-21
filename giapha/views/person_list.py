"""Person list (search/filter/paginate) + bulk/single create.

Split out of `views/person.py` to keep that file under 200 lines, mirroring
how phase 2 split `views/clan.py` into two modules. Creation runs
through `selectors.person_write.apply_person_create_many` (shared with
change-request approval), which loads the edge set ONCE per request and
updates it in memory as the batch is walked.
"""

from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.permissions import IsClanMember
from giapha.permissions_scope import require_write
from giapha.selectors.person import search_persons
from giapha.selectors.person_write import apply_person_create_many
from giapha.serializers.person import PersonReadSerializer, PersonWriteSerializer
from giapha.services.person_rules import PersonValidationError

MAX_BULK_CREATE = 200
# Bounds Django's `YearLookup` (builds `datetime.date(year, 1, 1)`) against a
# stdlib `OverflowError` on an out-of-range year -- `int()` alone accepts any
# size.
MIN_DEATH_YEAR = 1
MAX_DEATH_YEAR = 9999


class PersonPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 200


def _int_query_param(request, name, min_value=None, max_value=None):
    """`None` if `name` is absent from the query string; the parsed `int`
    if present, valid, and within `[min_value, max_value]`; a 400 naming the
    parameter otherwise.
    """
    raw = request.query_params.get(name)
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        raise BadRequestException('Tham số {} phải là số nguyên.'.format(name))
    if min_value is not None and value < min_value:
        raise BadRequestException('Tham số {} phải từ {} trở lên.'.format(name, min_value))
    if max_value is not None and value > max_value:
        raise BadRequestException('Tham số {} phải nhỏ hơn hoặc bằng {}.'.format(name, max_value))
    return value


def _wants_force(request, clan_id):
    """`?force=true` bypasses `parent_born_before_child`. Only the clan
    owner may use it -- real gia phả data is often approximate, but an
    editor bypassing the 12-year sanity check unsupervised is not the
    intended escape hatch.
    """
    raw = request.query_params.get('force')
    if raw is None:
        return False
    wants = raw.lower() in ('1', 'true')
    if wants and request._giapha_role_cache.get(clan_id) != 'owner':
        raise PermissionDenied('Chỉ chủ sở hữu mới có thể dùng force=true.')
    return wants


class PersonListCreateAPIView(APIView):
    """`GET` lists (paginated, search/filterable) non-deleted persons.
    `POST` creates one (a JSON object) or many (a JSON array, capped at
    `MAX_BULK_CREATE`).
    """

    permission_classes = [IsAuthenticated, IsClanMember]

    def get(self, request, clan_id):
        queryset = search_persons(
            clan_id,
            q=request.query_params.get('q'),
            generation=_int_query_param(request, 'generation'),
            branch=request.query_params.get('branch'),
            death_year=_int_query_param(request, 'death_year', min_value=MIN_DEATH_YEAR, max_value=MAX_DEATH_YEAR),
        )
        paginator = PersonPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return Response({
            'data': PersonReadSerializer(page, many=True).data,
            'count': paginator.count,
            'next': paginator.get_next_link(),
            'previous': paginator.get_previous_link(),
        })

    def post(self, request, clan_id):
        is_bulk = isinstance(request.data, list)
        raw_items = request.data if is_bulk else [request.data]
        if len(raw_items) > MAX_BULK_CREATE:
            raise BadRequestException(
                'Tối đa {} bản ghi cho mỗi lần ghi hàng loạt.'.format(MAX_BULK_CREATE)
            )
        if len(raw_items) == 0:
            raise BadRequestException('Danh sách thành viên không được để trống.')

        serializer = PersonWriteSerializer(data=raw_items, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # A verified member may add a person under parents in their family
        # scope -- EVERY given parent (review L3: an in-scope father must not
        # let an arbitrary outsider be set as mother). Checked for every item
        # before anything is written: one bad item rejects the whole batch.
        for item in serializer.validated_data:
            require_write(request, clan_id, [item.get('father_id'), item.get('mother_id')])

        force = _wants_force(request, clan_id)
        try:
            created = apply_person_create_many(clan_id, serializer.validated_data, request.user, force=force)
        except PersonValidationError as exc:
            raise BadRequestException(str(exc))

        out = PersonReadSerializer(created, many=True).data
        return Response({'data': out if is_bulk else out[0]}, status=status.HTTP_201_CREATED)
