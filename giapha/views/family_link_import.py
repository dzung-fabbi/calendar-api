"""`POST /v1/family/links/import` -- "nhận về" (plan 260919 phase 4).

Copies chosen clan persons into the personal tree (shared fields only) and
links them. Then rebuilds the edges the clan has between linked people --
parent slots and spouse pairs -- where at least one end is newly imported,
using the SAME personal-tree rules as a manual edit (`services.family_rules`).
An edge that breaks a rule, or would overwrite an occupied parent slot, is
skipped and reported in `skippedEdges`; existing personal structure is never
changed.
"""

from django.conf import settings
from django.db import transaction

from giapha.selectors.family import load_graph
from giapha.selectors.family_link import clan_marriage_pairs, clan_person_rows, links_in_clan
from giapha.selectors.family_link_write import import_clan_persons
from giapha.selectors.family_write import set_parent_slot, upsert_spouse
from giapha.serializers.family_link import LinkImportSerializer
from giapha.services.family_graph import SLOTS
from giapha.services.family_issue import MESSAGES, FamilyRuleError
from giapha.services.family_rules import check_link_spouse, check_set_parent, check_slot_free
from giapha.views.family_base import FamilyAPIView, id_str
from giapha.views.family_link import FamilyLinkedResponseMixin, require_member


def _connect_parents(graph, clan_rows, to_family, new_family_ids, skipped):
    for row in clan_rows:
        child = to_family.get(row['id'])
        if child is None:
            continue
        for slot in SLOTS:
            parent = to_family.get(row[slot + '_id'])
            if parent is None or (child not in new_family_ids and parent not in new_family_ids):
                continue
            if graph.parent_in_slot(child, slot) == parent:
                continue
            try:
                check_slot_free(graph, child, slot, parent)
                check_set_parent(graph, child, slot, parent)
            except FamilyRuleError as exc:
                skipped.append(exc.to_error())
                continue
            set_parent_slot(child, slot, parent)
            graph.set_parent(child, slot, parent)


def _connect_spouses(family, graph, marriages, to_family, new_family_ids, skipped):
    for husband, wife, status in marriages:
        a, b = to_family.get(husband), to_family.get(wife)
        if a is None or b is None or (a not in new_family_ids and b not in new_family_ids):
            continue
        if b in graph.spouses_of(a):
            continue
        try:
            check_link_spouse(graph, a, b)
        except FamilyRuleError as exc:
            skipped.append(exc.to_error())
            continue
        spouse_type = 'divorced' if status == 'ly_hon' else 'married'
        upsert_spouse(family, a, b, spouse_type)
        graph.add_spouse(a, b, spouse_type)


class FamilyLinkImportAPIView(FamilyLinkedResponseMixin, FamilyAPIView):
    def post(self, request):
        body = self.validate(LinkImportSerializer, request.data)
        clan_id = body['clanId']
        require_member(request.user, clan_id)

        clan_rows = clan_person_rows(clan_id)
        by_id = {row['id']: row for row in clan_rows}
        wanted = list(dict.fromkeys(body['clanPersonIds']))
        missing = [cid for cid in wanted if cid not in by_id]
        if missing:
            raise FamilyRuleError('CLAN_PERSON_NOT_FOUND', other_id=missing[0], status=404)

        with transaction.atomic():
            already = set(links_in_clan(self.family, clan_id).values())
            new_rows = [by_id[cid] for cid in wanted if cid not in already]
            _persons, _spouses, graph = load_graph(self.family.id)
            limit = settings.FAMILY_MAX_PERSONS
            if len(graph.persons) + len(new_rows) > limit:
                raise FamilyRuleError('FAMILY_FULL', message=MESSAGES['FAMILY_FULL'].format(limit))
            created = import_clan_persons(self.family, clan_id, new_rows, request.user)
            to_family = {cid: fid for fid, cid in links_in_clan(self.family, clan_id).items()}
            _persons, _spouses, graph = load_graph(self.family.id)
            new_ids = set(created.values())
            skipped = []
            _connect_parents(graph, clan_rows, to_family, new_ids, skipped)
            _connect_spouses(self.family, graph, clan_marriage_pairs(clan_id), to_family, new_ids, skipped)

        return self.linked_response(
            status=201,
            imported={str(cid): id_str(fid) for cid, fid in created.items()},
            skippedEdges=skipped,
        )
