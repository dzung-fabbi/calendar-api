"""`POST /clans/{clan_id}/change-requests/{cr_id}/approve` and `/reject`.

Reviewer = editor+ who may write every person the proposal touches
(`permissions_scope`; a branch editor only reviews inside their branch).
Approve runs in one transaction with the proposal row locked, so two
reviewers clicking at once apply it once. A target edited after the proposal
answers 409 `stale` unless `override_stale=true`; a vanished target marks the
proposal `stale` for good.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.notifications import push_to_users
from giapha.permissions import EDITOR_ROLES, IsClanEditor, cached_member
from giapha.permissions_scope import can_write_any, can_write_persons
from giapha.selectors.change_request import get_change_request_for_update, reviewer_members
from giapha.selectors.scope import scope_graph
from giapha.services.family_scope import branch_scope_ids
from giapha.selectors.family_link_write import link_contributed_person
from giapha.selectors.person_version import VersionConflict
from giapha.selectors.change_request_apply import (
    STALE_GONE,
    apply_change_request,
    live_target_marriage,
    live_target_person,
    staleness,
    target_ids,
)
from giapha.serializers.change_request import (
    ChangeRequestApproveSerializer,
    ChangeRequestRejectSerializer,
    ChangeRequestSerializer,
)
from giapha.serializers.marriage import MarriageSerializer
from giapha.serializers.person import PersonReadSerializer
from giapha.services.person_rules import PersonValidationError

CR_NOT_FOUND = 'Không tìm thấy đề xuất.'
NOT_PENDING_DETAIL = 'Đề xuất này không còn chờ duyệt.'
OUT_OF_REVIEW_SCOPE = 'Đề xuất này nằm ngoài phạm vi bạn được duyệt.'
STALE_DETAIL = 'Dữ liệu đã được sửa sau khi gửi đề xuất. Xem lại rồi duyệt với override_stale=true.'


def current_state(cr):
    """What the target looks like now -- the client renders a diff against it."""
    person = live_target_person(cr)
    if person is not None:
        return PersonReadSerializer(person).data
    marriage = live_target_marriage(cr)
    return MarriageSerializer(marriage).data if marriage is not None else None


def can_review(request, clan_id, cr):
    member = cached_member(request, clan_id)
    if member is None or member.role not in EDITOR_ROLES:
        return False
    ids, any_of = target_ids(cr)
    return (can_write_any if any_of else can_write_persons)(request, clan_id, ids)


def reviewer_user_ids(clan_id, cr):
    """Who is pushed about `cr`: owner, managers, whole-clan editors, and
    branch editors whose branch holds the target (phase 6)."""
    members = reviewer_members(clan_id)
    if not any(member.scope_root_person_id for member in members):
        return [member.user_id for member in members]
    ids, any_of = target_ids(cr)
    wanted = {pid for pid in ids if pid is not None}
    edges, marriages, _verified = scope_graph(clan_id)
    out = []
    for member in members:
        if member.role != 'editor' or not member.scope_root_person_id:
            out.append(member.user_id)
            continue
        branch = branch_scope_ids(edges, marriages, member.scope_root_person_id)
        if wanted and ((wanted & branch) if any_of else wanted <= branch):
            out.append(member.user_id)
    return out


def _locked_reviewable(request, clan_id, cr_id):
    cr = get_change_request_for_update(clan_id, cr_id)
    if cr is None:
        raise NotFound(CR_NOT_FOUND)
    if not can_review(request, clan_id, cr):
        raise PermissionDenied(OUT_OF_REVIEW_SCOPE)
    if cr.status != 'pending':
        raise BadRequestException(NOT_PENDING_DETAIL)
    return cr


def _close(cr, request, new_status, note):
    cr.status = new_status
    cr.reviewer = request.user
    cr.review_note = note
    cr.reviewed_at = timezone.now()
    cr.save(update_fields=['status', 'reviewer', 'review_note', 'reviewed_at'])
    push_to_users(
        [cr.proposer_id], 'Đề xuất đã được xử lý',
        'Đề xuất sửa gia phả của bạn: {}.'.format(cr.get_status_display().lower())
        + (' Ghi chú: {}'.format(note) if note else ''),
        {'type': 'change_request_' + new_status, 'clan_id': cr.clan_id, 'change_request_id': cr.id},
    )


class ChangeRequestApproveAPIView(APIView):
    permission_classes = [IsAuthenticated, IsClanEditor]

    def post(self, request, clan_id, cr_id):
        body = ChangeRequestApproveSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        note, override = body.validated_data['note'], body.validated_data['override_stale']

        with transaction.atomic():
            cr = _locked_reviewable(request, clan_id, cr_id)
            stale = staleness(cr)
            if stale == STALE_GONE:
                _close(cr, request, 'stale', note)
                return Response({'code': 'stale', 'detail': STALE_DETAIL}, status=status.HTTP_409_CONFLICT)
            if stale and not override:
                return Response(
                    {'code': 'stale', 'detail': STALE_DETAIL, 'current': current_state(cr)},
                    status=status.HTTP_409_CONFLICT,
                )
            try:
                with transaction.atomic():
                    result = apply_change_request(
                        cr, request.user, expected_version=None if override else cr.base_version)
            except PersonValidationError as exc:
                raise BadRequestException(str(exc))
            except VersionConflict:
                return Response(
                    {'code': 'stale', 'detail': STALE_DETAIL, 'current': current_state(cr)},
                    status=status.HTTP_409_CONFLICT,
                )
            link_contributed_person(cr, result)
            _close(cr, request, 'approved', note)

        data = ChangeRequestSerializer(cr).data
        data['result_id'] = getattr(result, 'id', None)
        return Response({'data': data})


class ChangeRequestRejectAPIView(APIView):
    permission_classes = [IsAuthenticated, IsClanEditor]

    def post(self, request, clan_id, cr_id):
        body = ChangeRequestRejectSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        with transaction.atomic():
            cr = _locked_reviewable(request, clan_id, cr_id)
            _close(cr, request, 'rejected', body.validated_data['note'])
        return Response({'data': ChangeRequestSerializer(cr).data})
