"""Person list (search/filter/paginate) + bulk/single create.

Split out of `views/person.py` to keep that file under 200 lines, mirroring
how phase 2 split `views/clan.py` into two modules. `clan_edges`/
`birth_solar_by_id` are loaded ONCE per request (even for a 200-row bulk
create) and updated in memory as the batch is walked, so validating record N
doesn't cost N queries.
"""

from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.models import Person
from giapha.permissions import IsClanEditor, IsClanMember
from giapha.selectors.person import active_person_count, birth_solar_by_id, clan_edges, search_persons
from giapha.selectors.revision import record
from giapha.serializers.person import PersonReadSerializer, PersonWriteSerializer
from giapha.services.person_rules import PersonValidationError, ids_from_edges, validate_person_write
from giapha.services.tree import compute_generations

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

    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        classes = [IsClanMember] if self.request.method in SAFE_METHODS else [IsClanEditor]
        return [IsAuthenticated()] + [cls() for cls in classes]

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

        force = _wants_force(request, clan_id)
        created = self._create_all(clan_id, serializer.validated_data, request.user, force)

        out = PersonReadSerializer(created, many=True).data
        return Response({'data': out if is_bulk else out[0]}, status=status.HTTP_201_CREATED)

    @staticmethod
    def _create_all(clan_id, items, actor, force):
        edges = clan_edges(clan_id)
        ids_in_clan = ids_from_edges(edges)
        birth_map = birth_solar_by_id(clan_id)
        person_count = active_person_count(clan_id)

        created = []
        with transaction.atomic():
            for item in items:
                try:
                    validate_person_write(
                        item, edges=edges, ids_in_clan=ids_in_clan, birth_map=birth_map,
                        existing_count=person_count, max_persons=settings.MAX_CLAN_PERSONS,
                        force=force, person_id=None,
                    )
                except PersonValidationError as exc:
                    raise BadRequestException(str(exc))

                person = Person.objects.create(clan_id=clan_id, **item)
                record(person, actor=actor, action='create')

                edges.append((person.id, item.get('father_id'), item.get('mother_id')))
                ids_in_clan.add(person.id)
                birth_map[person.id] = item.get('birth_solar')
                person_count += 1
                created.append(person)

            # `generation` is derived state (H1): compute it for every row
            # just inserted, over the FULL updated edge set -- a new row can
            # be the parent of another new row later in the same batch, so
            # the edge list must include everything created so far. One pass
            # over the whole batch is enough; nothing here recurses per row.
            generations = compute_generations(edges)
            for person in created:
                person.generation = generations.get(person.id)
            Person.objects.bulk_update(created, ['generation'])

        # Re-fetch through the selector-equivalent query instead of reusing
        # the in-memory `created` instances (H2): those have empty
        # `father`/`mother` relation caches, so `PersonReadSerializer.
        # get_father_name` would issue one SELECT per row with a parent set.
        # One extra query total, regardless of batch size, replaces what
        # would otherwise be O(n) queries. `order_by('id')` preserves
        # creation order (MySQL auto-increment is monotonic per connection).
        return list(
            Person.objects.filter(id__in=[person.id for person in created])
            .select_related('father', 'mother')
            .order_by('id')
        )
