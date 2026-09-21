"""Person detail/update/soft-delete. List/create lives in `views/person_list.py`
(split to keep both files under 200 lines).

Writes go through `selectors.person_write` -- the same path change-request
approval uses -- which runs `services.person_rules`, records a revision and
recomputes generations when parents change.
"""

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.permissions import IsClanMember
from giapha.permissions_scope import can_edit_mode, require_parent_change_write, require_write
from giapha.selectors.person import get_person_or_none
from giapha.selectors.person_version import VersionConflict
from giapha.selectors.person_write import apply_person_delete, apply_person_update
from giapha.serializers.person import PersonReadSerializer, PersonWriteSerializer
from giapha.services.person_rules import PersonValidationError

PERSON_NOT_FOUND = 'Không tìm thấy thành viên.'
VERSION_CONFLICT_DETAIL = 'Người này vừa được người khác sửa. Hãy xem bản mới nhất rồi sửa lại.'


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


def _expected_version(request):
    """Optional `version` in the PATCH body (plan 260919 phase 5). Absent
    means no check, so clients predating versions keep working."""
    raw = request.data.get('version') if hasattr(request.data, 'get') else None
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 1:
        raise BadRequestException('Tham số version phải là số nguyên dương.')
    return raw


def _detail_payload(request, clan_id, person):
    """Detail shape + `can_edit` ('direct' | 'propose') for the caller."""
    # `with_photo_url`: this is the detail response the phase-08 spec
    # scopes `photo_url` to (H3) -- see `PersonReadSerializer.get_photo_url`.
    data = PersonReadSerializer(person, context={'with_photo_url': True}).data
    data['can_edit'] = can_edit_mode(request, clan_id, person.id)
    return {'data': data}


class PersonDetailAPIView(APIView):
    """`GET` for any member. `PATCH`/`DELETE` (soft) for editor+, or a
    verified member inside their family scope (`permissions_scope`).
    """

    permission_classes = [IsAuthenticated, IsClanMember]

    def get(self, request, clan_id, person_id):
        person = get_person_or_none(clan_id, person_id)
        if person is None:
            raise NotFound(PERSON_NOT_FOUND)
        return Response(_detail_payload(request, clan_id, person))

    def patch(self, request, clan_id, person_id):
        person = get_person_or_none(clan_id, person_id)
        if person is None:
            raise NotFound(PERSON_NOT_FOUND)
        require_write(request, clan_id, [person.id])

        serializer = PersonWriteSerializer(person, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        changed_parents = {
            key: value for key, value in serializer.validated_data.items()
            if key in ('father_id', 'mother_id') and value != getattr(person, key)
        }
        require_parent_change_write(request, clan_id, changed_parents)
        force = _wants_force(request, clan_id)
        expected = _expected_version(request)
        try:
            apply_person_update(
                clan_id, person, serializer.validated_data, request.user, force=force, expected_version=expected,
            )
        except PersonValidationError as exc:
            raise BadRequestException(str(exc))
        except VersionConflict:
            current = get_person_or_none(clan_id, person_id)
            return Response(
                {'code': 'VERSION_CONFLICT', 'detail': VERSION_CONFLICT_DETAIL,
                 'current': PersonReadSerializer(current).data},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(_detail_payload(request, clan_id, person))

    def delete(self, request, clan_id, person_id):
        person = get_person_or_none(clan_id, person_id)
        if person is None:
            raise NotFound(PERSON_NOT_FOUND)
        require_write(request, clan_id, [person.id])
        try:
            apply_person_delete(person, request.user)
        except PersonValidationError as exc:
            raise BadRequestException(str(exc))
        return Response(status=status.HTTP_204_NO_CONTENT)
