"""Person detail/update/soft-delete. List/create lives in `views/person_list.py`
(split to keep both files under 200 lines).

Write endpoints run `services.person_rules` before touching the database.
`father_id`/`mother_id` changing on `PATCH` also triggers a descendant-subtree
`generation` recompute -- see `selectors.tree.recompute_descendant_generations`.
"""

from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.permissions import IsClanEditor, IsClanMember
from giapha.selectors.person import birth_solar_by_id, children_count, clan_edges, get_person_or_none
from giapha.selectors.revision import record
from giapha.selectors.tree import recompute_descendant_generations
from giapha.serializers.person import PersonReadSerializer, PersonWriteSerializer
from giapha.services.person_rules import PersonValidationError, ids_from_edges, validate_person_write

PERSON_NOT_FOUND = 'Không tìm thấy thành viên.'
# The fields `validate_person_write` cares about; used to build the "merged
# current + incoming" payload for a partial update.
_RULE_FIELDS = ('father_id', 'mother_id', 'birth_solar', 'death_solar', 'death_lunar_day', 'death_lunar_month')
# `father_id`/`mother_id` changing is what triggers the descendant-subtree
# generation recompute after a PATCH.
_PARENT_FIELDS = ('father_id', 'mother_id')


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


class PersonDetailAPIView(APIView):
    """`GET` for any member. `PATCH`/`DELETE` (soft) for editor+."""

    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        classes = [IsClanMember] if self.request.method in SAFE_METHODS else [IsClanEditor]
        return [IsAuthenticated()] + [cls() for cls in classes]

    def get(self, request, clan_id, person_id):
        person = get_person_or_none(clan_id, person_id)
        if person is None:
            raise NotFound(PERSON_NOT_FOUND)
        # `with_photo_url`: this is the detail response the phase-08 spec
        # scopes `photo_url` to (H3) -- see `PersonReadSerializer.get_photo_url`.
        return Response({'data': PersonReadSerializer(person, context={'with_photo_url': True}).data})

    def patch(self, request, clan_id, person_id):
        person = get_person_or_none(clan_id, person_id)
        if person is None:
            raise NotFound(PERSON_NOT_FOUND)

        serializer = PersonWriteSerializer(person, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        force = _wants_force(request, clan_id)
        edges = clan_edges(clan_id)
        merged = {field: getattr(person, field) for field in _RULE_FIELDS}
        merged.update({k: v for k, v in serializer.validated_data.items() if k in _RULE_FIELDS})

        try:
            validate_person_write(
                merged, edges=edges, ids_in_clan=ids_from_edges(edges),
                birth_map=birth_solar_by_id(clan_id), existing_count=0,
                max_persons=settings.MAX_CLAN_PERSONS, force=force, person_id=person.id,
            )
        except PersonValidationError as exc:
            raise BadRequestException(str(exc))

        parent_changed = any(
            field in serializer.validated_data and serializer.validated_data[field] != getattr(person, field)
            for field in _PARENT_FIELDS
        )

        with transaction.atomic():
            record(person, actor=request.user, action='update')
            for field, value in serializer.validated_data.items():
                setattr(person, field, value)
            person.save()

            if parent_changed:
                # Only the descendant subtree, not the whole clan -- see
                # `selectors.tree.recompute_descendant_generations`. This
                # person is always in its own target set, so its in-memory
                # `generation` (serialized below) may now be stale.
                recompute_descendant_generations(clan_id, person.id)
                person.refresh_from_db(fields=['generation'])

        return Response({'data': PersonReadSerializer(person, context={'with_photo_url': True}).data})

    def delete(self, request, clan_id, person_id):
        person = get_person_or_none(clan_id, person_id)
        if person is None:
            raise NotFound(PERSON_NOT_FOUND)

        blocking = children_count(person.id)
        if blocking:
            raise BadRequestException(
                'Không thể xoá vì còn {} người con đang tham chiếu người này làm cha/mẹ.'.format(blocking)
            )

        with transaction.atomic():
            record(person, actor=request.user, action='delete')
            person.is_deleted = True
            person.save(update_fields=['is_deleted'])

        return Response(status=status.HTTP_204_NO_CONTENT)
