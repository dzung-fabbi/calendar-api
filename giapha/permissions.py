"""Permission classes shared by every giapha view.

All three read `clan_id` from `view.kwargs` and cache the resolved role on
`request._giapha_role_cache` (a dict keyed by clan_id) so stacking several of
these checks -- or a permission check plus a serializer that also needs the
role -- costs at most one query per request, not one per check.

Outsiders (authenticated users who are not a member of the clan) always get
404 via `NotFound`, never 403 -- a 403 would confirm the clan exists.
"""

from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission

from giapha.models.choices import APPROVER_ROLES, EDITOR_ROLES  # noqa: F401 (re-exported)
from giapha.selectors.clan import clan_member_for

NOT_FOUND_DETAIL = 'Không tìm thấy dòng họ.'


def cached_member(request, clan_id):
    """The caller's `ClanMember` row for `clan_id` as cached by `_role_for`,
    or None. Only meaningful after a permission class ran for that clan.
    """
    return getattr(request, '_giapha_member_cache', {}).get(clan_id)


def _role_for(request, view):
    """Resolve + cache the caller's role for `view.kwargs['clan_id']`.

    Raises `NotFound` when the caller is not a member of the clan (or the
    clan is soft-deleted) -- callers that need "member but wrong role" (403)
    check the returned role themselves instead of relying on this raising.
    """
    clan_id = view.kwargs.get('clan_id')
    cache = getattr(request, '_giapha_role_cache', None)
    if cache is None:
        cache = {}
        request._giapha_role_cache = cache
    if clan_id not in cache:
        member = clan_member_for(request.user, clan_id)
        cache[clan_id] = member.role if member else None
        member_cache = getattr(request, '_giapha_member_cache', None)
        if member_cache is None:
            member_cache = {}
            request._giapha_member_cache = member_cache
        member_cache[clan_id] = member
    role = cache[clan_id]
    if role is None:
        raise NotFound(NOT_FOUND_DETAIL)
    return role


class IsClanMember(BasePermission):
    """Any role qualifies."""

    message = 'Bạn không phải thành viên dòng họ này.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        _role_for(request, view)
        return True


class IsClanEditor(BasePermission):
    """owner, manager or editor."""

    message = 'Chỉ chủ sở hữu hoặc biên tập viên mới có quyền này.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return _role_for(request, view) in EDITOR_ROLES


class IsClanApprover(BasePermission):
    """owner or manager (Ban quản lý)."""

    message = 'Chỉ trưởng họ hoặc Ban quản lý mới có quyền này.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return _role_for(request, view) in APPROVER_ROLES


class IsClanOwner(BasePermission):
    """owner only."""

    message = 'Chỉ chủ sở hữu mới có quyền này.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return _role_for(request, view) == 'owner'
