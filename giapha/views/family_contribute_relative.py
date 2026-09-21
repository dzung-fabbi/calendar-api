"""`add-relative` with `contributeTo: [clanId]` (plan 260919 phase 5).

After the relative is created in the personal tree, contribute it to each
clan through the same path as `POST /v1/family/links/contribute`. Its clan
parents are its personal parents' LINKED counterparts in that clan (none if
they are not linked). A failure for one clan is reported in that clan's
entry -- the personal write already happened and is never rolled back.
"""

from giapha.selectors.family import get_person_or_none
from giapha.selectors.family_link import links_in_clan
from giapha.services.family_issue import FamilyRuleError
from giapha.views.family_link_contribute import contribute_person


def contribute_new_relative(user, family, person_id, clan_id):
    person = get_person_or_none(family.id, person_id)
    linked = links_in_clan(family, clan_id)
    parents = [linked.get(person.father_id), linked.get(person.mother_id)]
    try:
        return contribute_person(user, family, person, clan_id, parents)
    except FamilyRuleError as exc:
        return {'clanId': clan_id, 'result': 'error', 'error': exc.to_error()}
