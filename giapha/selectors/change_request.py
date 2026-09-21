"""DB reads for ChangeRequest (đề xuất thay đổi)."""

from giapha.models import ChangeRequest, ClanMember
from giapha.models.choices import EDITOR_ROLES

MAX_PENDING_PER_PROPOSER = 20


def change_requests_of(clan_id, status=None, proposer_id=None):
    queryset = (
        ChangeRequest.objects.filter(clan_id=clan_id)
        .select_related('proposer', 'reviewer', 'target_marriage')
        .order_by('-created_at')
    )
    if status:
        queryset = queryset.filter(status=status)
    if proposer_id is not None:
        queryset = queryset.filter(proposer_id=proposer_id)
    return queryset


def get_change_request(clan_id, cr_id):
    return (
        ChangeRequest.objects.filter(clan_id=clan_id, id=cr_id)
        .select_related('proposer', 'reviewer', 'target_person', 'target_marriage')
        .first()
    )


def get_change_request_for_update(clan_id, cr_id):
    """Lock one proposal for approve/reject/withdraw. Caller must be in `atomic()`."""
    return ChangeRequest.objects.select_for_update().filter(clan_id=clan_id, id=cr_id).first()


def pending_count_for(clan_id, proposer_id):
    return ChangeRequest.objects.filter(clan_id=clan_id, proposer_id=proposer_id, status='pending').count()


def reviewer_members(clan_id):
    """`ClanMember` rows (editor+) that may review proposals in `clan_id`.
    Rows, not ids: phase 6 narrows by each editor's branch scope.
    """
    return list(
        ClanMember.objects.filter(clan_id=clan_id, role__in=EDITOR_ROLES)
        .only('id', 'user_id', 'role', 'scope_root_person_id')
    )


def pending_created_before(cutoff):
    """Every pending proposal older than `cutoff`, across clans (daily job)."""
    return list(
        ChangeRequest.objects.filter(status='pending', created_at__lte=cutoff, clan__is_deleted=False)
        .order_by('clan_id', 'id')
    )
