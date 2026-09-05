"""Revision history + restore for a Person.

Split out of `views/person.py` to keep that file under 200 lines, mirroring
how phase 2 split `views/clan.py` into two modules.
"""

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import NotFound
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.permissions import IsClanEditor
from giapha.selectors.person import birth_solar_by_id, clan_edges, get_person_any
from giapha.serializers.person import PersonReadSerializer, PersonRevisionSerializer
from giapha.selectors.revision import record, revision_for_person, revisions_of
from giapha.services.person_rules import PersonValidationError, ids_from_edges, validate_person_write
from giapha.services.revision import restore

PERSON_NOT_FOUND = 'Không tìm thấy thành viên.'
REVISION_NOT_FOUND = 'Không tìm thấy bản ghi lịch sử.'
# The fields `validate_person_write` cares about -- same set `views/person.py`
# uses to build its "merged current + incoming" payload for a PATCH.
_RULE_FIELDS = ('father_id', 'mother_id', 'birth_solar', 'death_solar', 'death_lunar_day', 'death_lunar_month')


class RevisionPagination(LimitOffsetPagination):
    default_limit = 50
    max_limit = 200


class PersonRevisionListAPIView(APIView):
    """`GET` the change history of one person, newest first. Editor+ only --
    a revision's `payload_json` is a full field dump, not for viewers.
    """

    permission_classes = [IsAuthenticated, IsClanEditor]

    def get(self, request, clan_id, person_id):
        # `get_person_any`, not `get_person_or_none`: a soft-deleted person's
        # history must stay reachable.
        person = get_person_any(clan_id, person_id)
        if person is None:
            raise NotFound(PERSON_NOT_FOUND)

        revisions = revisions_of(person)
        paginator = RevisionPagination()
        page = paginator.paginate_queryset(revisions, request, view=self)
        return Response({
            'data': PersonRevisionSerializer(page, many=True).data,
            'count': paginator.count,
            'next': paginator.get_next_link(),
            'previous': paginator.get_previous_link(),
        })


class PersonRestoreAPIView(APIView):
    """`POST` re-applies a prior revision's snapshot onto the person. The
    current (pre-restore) state is itself recorded as a new revision first,
    so restoring is never a one-way trip.

    The restored payload is run through the same `validate_person_write` the
    normal PATCH path uses, against the CURRENT tree state, before it is
    persisted (H3) -- a revision recorded when the tree looked different
    (e.g. before another edit reshuffled parents into what would now be a
    cycle) must not bypass the rule that write path enforces on everyone
    else. `is_deleted`/`clan_id` are excluded from the snapshot itself (see
    `services.revision._EXCLUDED_FIELDS`), so restoring can never resurrect a
    soft-deleted person as a side effect.
    """

    permission_classes = [IsAuthenticated, IsClanEditor]

    def post(self, request, clan_id, person_id, revision_id):
        person = get_person_any(clan_id, person_id)
        if person is None:
            raise NotFound(PERSON_NOT_FOUND)

        revision = revision_for_person(person, revision_id)
        if revision is None:
            raise NotFound(REVISION_NOT_FOUND)

        edges = clan_edges(clan_id)
        with transaction.atomic():
            record(person, actor=request.user, action='update')
            restore(person, revision.payload_json)

            merged = {field: getattr(person, field) for field in _RULE_FIELDS}
            try:
                validate_person_write(
                    merged, edges=edges, ids_in_clan=ids_from_edges(edges),
                    birth_map=birth_solar_by_id(clan_id), existing_count=0,
                    max_persons=settings.MAX_CLAN_PERSONS, force=False, person_id=person.id,
                )
            except PersonValidationError as exc:
                raise BadRequestException(str(exc))

            person.save()

        return Response({'data': PersonReadSerializer(person).data})
