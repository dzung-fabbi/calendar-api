"""`POST /v1/family/clans` -- tạo dòng họ từ một nhánh của cây cá nhân
(plan 260919 phase 4, spec §14.3).

Copies the root, its descendants and all their spouses into a NEW clan
(caller = owner), links every copy back to its personal node, and binds the
owner to the copy of their `selfId` (verified) when "tôi" is in the branch.
One transaction; capped at `MAX_CLAN_PERSONS`. Unlike `POST /clans` (empty
clan), this starts populated. The copy reads the OVERLAID values, so a
person already linked elsewhere is copied as the user currently sees them.

"Nhận về" and "đóng góp" live in `views/family_link_import.py` and
`views/family_link_contribute.py`.
"""

from django.conf import settings
from django.db import transaction

from giapha.selectors.family import load_graph
from giapha.selectors.family_link_write import bootstrap_clan
from giapha.serializers.family_link import ClanBootstrapSerializer
from giapha.serializers.family_output import overlay_links
from giapha.services.family_clan_bootstrap import plan_bootstrap
from giapha.services.family_issue import MESSAGES, FamilyRuleError, not_found
from giapha.views.family_base import FamilyAPIView, id_str
from giapha.views.family_link import FamilyLinkedResponseMixin


class FamilyClanBootstrapAPIView(FamilyLinkedResponseMixin, FamilyAPIView):
    def post(self, request):
        body = self.validate(ClanBootstrapSerializer, request.data)
        root_id = body['rootPersonId']
        persons, spouses, graph = load_graph(self.family.id)
        if not graph.has(root_id):
            raise not_found(root_id)

        rows, _linked = overlay_links(persons, self.link_rows())
        ordered, marriages, skipped = plan_bootstrap(rows, spouses, root_id)
        if len(ordered) > settings.MAX_CLAN_PERSONS:
            raise FamilyRuleError('CLAN_TOO_LARGE', message=MESSAGES['CLAN_TOO_LARGE'].format(settings.MAX_CLAN_PERSONS))

        with transaction.atomic():
            clan = bootstrap_clan(
                request.user, self.family, {row['id']: row for row in rows}, ordered, marriages,
                body['tenHo'], body['thuyTo'], self.family.self_person_id,
            )
        return self.linked_response(
            status=201,
            clan={'id': clan.id, 'tenHo': clan.ten_ho},
            skippedSpouses=[{'personId': id_str(a), 'otherId': id_str(b)} for a, b in skipped],
        )
