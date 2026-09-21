"""Row-level write check for clan persons: "may this caller edit these ids?".

Role classes (`permissions.py`) answer "may this caller write at all"; this
module answers "which persons". Every write view on persons, marriages and
photos runs `IsClanMember` first (which caches the caller's `ClanMember` row)
and then `require_write(request, clan_id, ids)`.

    owner / manager / editor          -> whole clan (`writable_ids` = None)
    editor with `scope_root_person`   -> that branch (+ own family if verified)
    viewer with a VERIFIED binding    -> `services.family_scope.family_scope_ids`
    anyone else                       -> nothing (empty set)

The scope graph costs 2 queries and is cached on
`request._giapha_scope_cache[clan_id]`, so a view checking several ids (or a
serializer adding `can_edit`) pays it once. Callers with full access pay 0.
"""

from rest_framework.exceptions import PermissionDenied

from giapha.permissions import APPROVER_ROLES, EDITOR_ROLES, cached_member
from giapha.selectors.scope import is_unattached, scope_graph
from giapha.services.family_scope import branch_scope_ids, family_scope_ids

OUT_OF_SCOPE_DETAIL = 'Bạn chỉ sửa được người trong gia đình mình. Hãy gửi đề xuất.'

CAN_EDIT_DIRECT = 'direct'
CAN_EDIT_PROPOSE = 'propose'


def writable_ids_for_member(member, clan_id):
    """Same answer as `writable_ids`, for callers outside a clan-scoped URL
    (e.g. `/v1/family/links/contribute`) that loaded the member themselves."""
    if member is None:
        return set()
    branch_root = getattr(member, 'scope_root_person_id', None)
    if member.role in EDITOR_ROLES and not (member.role == 'editor' and branch_root):
        return None
    verified = bool(member.person_id and member.person_verified)
    if not (verified or member.role in EDITOR_ROLES):
        return set()
    parent_edges, marriage_pairs, verified_ids = scope_graph(clan_id)
    scope = set()
    if member.role in EDITOR_ROLES:
        scope |= branch_scope_ids(parent_edges, marriage_pairs, branch_root)
    if verified:
        scope |= family_scope_ids(parent_edges, marriage_pairs, member.person_id, verified_ids)
    return scope


def writable_ids(request, clan_id):
    """`None` = every person in the clan; otherwise the (possibly empty) set
    of person ids the caller may write directly.
    """
    cache = getattr(request, '_giapha_scope_cache', None)
    if cache is None:
        cache = {}
        request._giapha_scope_cache = cache
    if clan_id not in cache:
        cache[clan_id] = writable_ids_for_member(cached_member(request, clan_id), clan_id)
    return cache[clan_id]


def can_write_persons(request, clan_id, ids):
    """True when every id in `ids` is writable. `None` entries are ignored;
    an empty `ids` is True only for full-access callers.
    """
    scope = writable_ids(request, clan_id)
    if scope is None:
        return True
    wanted = {person_id for person_id in ids if person_id is not None}
    return bool(wanted) and wanted <= scope


def can_write_any(request, clan_id, ids):
    """True when at least one of `ids` is writable (marriages: one side is enough)."""
    scope = writable_ids(request, clan_id)
    if scope is None:
        return True
    return any(person_id in scope for person_id in ids if person_id is not None)


def require_write(request, clan_id, ids, any_of=False):
    """Raise 403 with the "send a proposal" hint unless the caller may write."""
    check = can_write_any if any_of else can_write_persons
    if not check(request, clan_id, ids):
        raise PermissionDenied(OUT_OF_SCOPE_DETAIL)


def require_parent_change_write(request, clan_id, data):
    """A scoped writer changing `father_id`/`mother_id` must also be able to
    write every NEW parent (review C1): re-parenting one's own node under an
    outsider would otherwise pull that outsider's family into scope."""
    new_parents = [data[key] for key in ('father_id', 'mother_id') if data.get(key)]
    if new_parents:
        require_write(request, clan_id, new_parents)


def require_marriage_write(request, clan_id, husband_id, wife_id):
    """Both partners writable, or one writable and the other `is_unattached`
    (review C2) -- a marriage must never pull an existing relative into scope."""
    scope = writable_ids(request, clan_id)
    if scope is None:
        return
    inside = [pid in scope for pid in (husband_id, wife_id)]
    if all(inside):
        return
    if any(inside):
        other = wife_id if inside[0] else husband_id
        if is_unattached(clan_id, other):
            return
    raise PermissionDenied(OUT_OF_SCOPE_DETAIL)


def invite_scope_ids(member, clan_id):
    """Who a member may invite with an immediately active, person-bound code
    (review C3). `None` = anyone (approvers, whole-clan editors). Otherwise
    only DOWNWARD: descendants of one's own node (or branch root) and their
    spouses, never the node/root itself nor its parents or siblings -- an
    invitee bound there would get a wider scope than the inviter has.
    """
    branch_root = getattr(member, 'scope_root_person_id', None)
    if member.role in APPROVER_ROLES or (member.role == 'editor' and not branch_root):
        return None
    parent_edges, marriage_pairs, _verified = scope_graph(clan_id)
    out = set()
    for root in (branch_root if member.role == 'editor' else None,
                 member.person_id if member.person_verified else None):
        if root:
            out |= branch_scope_ids(parent_edges, marriage_pairs, root) - {root}
    return out


def binding_auto_verified(member, clan_id, person_id):
    """A self-claim is verified on write only for approvers, whole-clan
    editors, and a branch editor claiming a node inside their branch (review H2)."""
    branch_root = getattr(member, 'scope_root_person_id', None)
    if member.role in APPROVER_ROLES or (member.role == 'editor' and not branch_root):
        return True
    if member.role != 'editor':
        return False
    parent_edges, marriage_pairs, _verified = scope_graph(clan_id)
    return person_id in branch_scope_ids(parent_edges, marriage_pairs, branch_root)


def can_verify_binding(request, clan_id, person_id):
    """Owner/manager verify anyone; a branch editor (trưởng chi) verifies
    nodes inside their branch; plain editors and viewers never."""
    member = cached_member(request, clan_id)
    if member is None:
        return False
    if member.role in APPROVER_ROLES:
        return True
    if member.role != 'editor' or not member.scope_root_person_id:
        return False
    parent_edges, marriage_pairs, _verified = scope_graph(clan_id)
    return person_id in branch_scope_ids(parent_edges, marriage_pairs, member.scope_root_person_id)


def can_edit_mode(request, clan_id, person_id):
    """`'direct'` or `'propose'` -- drives which button the client shows."""
    return CAN_EDIT_DIRECT if can_write_persons(request, clan_id, [person_id]) else CAN_EDIT_PROPOSE
