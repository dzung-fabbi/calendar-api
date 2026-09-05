"""Selector package. Re-exported flat so call sites stay short."""

from giapha.selectors.clan import (
    clan_role_for,
    clans_for_user,
    get_clan_or_none,
    get_invite_by_id,
    get_invite_for_update,
    invites_of,
    member_by_user_id,
    members_of,
    owner_count,
    roles_for_clans,
)
from giapha.selectors.gio import deceased_with_lunar_death
from giapha.selectors.gio_follow import (
    active_tokens_for,
    binding_map,
    follow_rows_for_user,
    member_binding,
    notified_pairs,
    overrides_for_clan,
    person_claimed_by_other,
)
from giapha.selectors.marriage import (
    get_marriage_or_none,
    marriages_of,
    next_order_for_husband,
    orders_for_husband,
)
from giapha.selectors.revision import record, revision_for_person, revisions_of
from giapha.selectors.person import (
    active_person_count,
    birth_solar_by_id,
    children_count,
    clan_edges,
    clan_edges_all,
    get_person_any,
    get_person_or_none,
    persons_of,
    search_persons,
)
from giapha.selectors.tree import recompute_descendant_generations, tree_payload

__all__ = [
    'active_person_count',
    'active_tokens_for',
    'binding_map',
    'birth_solar_by_id',
    'children_count',
    'clan_edges',
    'clan_edges_all',
    'clan_role_for',
    'clans_for_user',
    'deceased_with_lunar_death',
    'follow_rows_for_user',
    'get_clan_or_none',
    'get_invite_by_id',
    'get_invite_for_update',
    'get_marriage_or_none',
    'get_person_any',
    'get_person_or_none',
    'invites_of',
    'marriages_of',
    'member_binding',
    'member_by_user_id',
    'members_of',
    'next_order_for_husband',
    'notified_pairs',
    'orders_for_husband',
    'overrides_for_clan',
    'owner_count',
    'person_claimed_by_other',
    'persons_of',
    'recompute_descendant_generations',
    'revision_for_person',
    'revisions_of',
    'roles_for_clans',
    'search_persons',
    'tree_payload',
]
