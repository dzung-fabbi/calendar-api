"""`/v1/family/links` -- suggest, confirm, detach, diff (plan 260919 phase 4).

The caller must be a member of the clan named by `clanId`; anything else is
`CLAN_NOT_FOUND` (404), same "don't confirm the clan exists" rule as `/clans`.
Nothing here ever writes to the clan: links are personal-tree rows. Creating
clan data from a tree lives in `views/family_link_flow_clan.py`.
"""

from django.db import transaction
from rest_framework.response import Response

from giapha.selectors.clan import clan_member_for
from giapha.selectors.family import load_graph
from giapha.selectors.family_link import clan_marriage_pairs, clan_person_rows, get_link, links_in_clan
from giapha.selectors.family_link_detach import detach_links
from giapha.selectors.family_link_write import create_links
from giapha.serializers.family_link import ClanIdQuerySerializer, LinkCreateSerializer
from giapha.serializers.family_output import links_payload
from giapha.services.family_clan_diff import link_diff
from giapha.services.family_clan_matching import suggest_pairs
from giapha.services.family_issue import FamilyRuleError
from giapha.views.family_base import FamilyAPIView, id_str


def require_member(user, clan_id):
    member = clan_member_for(user, clan_id)
    if member is None:
        raise FamilyRuleError('CLAN_NOT_FOUND', status=404)
    return member


def family_match_rows(persons):
    return [{'id': row['id'], 'name': row['name'], 'father_id': row['father_id'],
             'mother_id': row['mother_id'], 'solar_birth_date': row['solar_birth_date']} for row in persons]


def spouse_pairs(spouses):
    return [(row['person_a_id'], row['person_b_id']) for row in spouses]


class FamilyLinkedResponseMixin:
    def linked_response(self, status=200, **extra):
        """Mutation envelope for link endpoints: fresh persons + links."""
        self._link_rows = None
        body = {'ok': True, 'persons': self.persons(), 'links': links_payload(self.link_rows())}
        body.update(extra)
        return Response(body, status=status)


class FamilyLinkSuggestionsAPIView(FamilyAPIView):
    def get(self, request):
        clan_id = self.validate(ClanIdQuerySerializer, request.query_params)['clanId']
        member = require_member(request.user, clan_id)
        persons, spouses, _graph = load_graph(self.family.id)
        if not persons:
            # Old users keep their tree on the device: import it first (§12).
            return Response({'suggestions': [], 'importRequired': True})

        anchor = (self.family.self_person_id, member.person_id) if member.person_id else None
        suggestions = suggest_pairs(
            family_match_rows(persons), spouse_pairs(spouses),
            clan_person_rows(clan_id), [(h, w) for h, w, _s in clan_marriage_pairs(clan_id)],
            links_in_clan(self.family, clan_id), anchor,
        )
        for item in suggestions:
            item['personId'] = id_str(item['personId'])
        return Response({'suggestions': suggestions, 'importRequired': False})


class FamilyLinkListCreateAPIView(FamilyLinkedResponseMixin, FamilyAPIView):
    def post(self, request):
        body = self.validate(LinkCreateSerializer, request.data)
        clan_id = body['clanId']
        require_member(request.user, clan_id)
        pairs = [(pair['personId'], pair['clanPersonId']) for pair in body['pairs']]

        _persons, _spouses, graph = load_graph(self.family.id)
        live_clan_ids = {row['id'] for row in clan_person_rows(clan_id)}
        for fid, cid in pairs:
            if not graph.has(fid):
                raise FamilyRuleError('PERSON_NOT_FOUND', person_id=fid, status=404)
            if cid not in live_clan_ids:
                raise FamilyRuleError('CLAN_PERSON_NOT_FOUND', person_id=fid, status=404)
        if len({fid for fid, _ in pairs}) != len(pairs) or len({cid for _, cid in pairs}) != len(pairs):
            raise FamilyRuleError('LINK_CONFLICT')
        if not create_links(self.family, clan_id, pairs, request.user):
            raise FamilyRuleError('LINK_CONFLICT')
        return self.linked_response(status=201)


class FamilyLinkDetailAPIView(FamilyLinkedResponseMixin, FamilyAPIView):
    def delete(self, request, link_id):
        """Tách: the family person keeps the clan's current shared values."""
        link = get_link(self.family, link_id)
        if link is None:
            raise FamilyRuleError('LINK_NOT_FOUND', status=404)
        with transaction.atomic():
            detach_links([link])
        return self.linked_response()


class FamilyLinkDiffAPIView(FamilyAPIView):
    def get(self, request):
        clan_id = self.validate(ClanIdQuerySerializer, request.query_params)['clanId']
        require_member(request.user, clan_id)
        persons, spouses, _graph = load_graph(self.family.id)
        items = link_diff(
            links_in_clan(self.family, clan_id), family_match_rows(persons), spouse_pairs(spouses),
            clan_person_rows(clan_id), [(h, w) for h, w, _s in clan_marriage_pairs(clan_id)],
        )
        return Response({'diffs': items})
