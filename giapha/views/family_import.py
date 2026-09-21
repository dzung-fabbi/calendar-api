"""`PUT /v1/family/import` -- one-off upload of an on-device (MMKV) tree.

Rules (spec §12, plan 260919 phase 3):
* only into an EMPTY server family -- otherwise 409 `FAMILY_NOT_EMPTY`,
  never an overwrite or a merge;
* idempotent on `importKey`: a retry after a dropped connection replays the
  stored `idMap` and creates nothing;
* every person is imported; broken edges are dropped into `skippedEdges`;
* throttled per user (`giapha-family-import`).

The Family row is locked for the whole request so two devices importing at
once serialize: the second sees a non-empty family and gets 409.
"""

from django.db import transaction
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from giapha.models import Family, FamilyPerson
from giapha.selectors.family_import_write import import_id_map, write_import
from giapha.serializers.family_import import FamilyImportSerializer
from giapha.services.family_import import plan_import
from giapha.services.family_issue import FamilyRuleError
from giapha.views.family_base import FamilyAPIView, id_str


class FamilyImportAPIView(FamilyAPIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'giapha-family-import'

    def put(self, request):
        body = self.validate(FamilyImportSerializer, request.data)
        import_key = body['import_key']

        with transaction.atomic():
            family = Family.objects.select_for_update().get(id=self.family.id)
            if family.import_key == import_key:
                return self._response(family, import_id_map(family.id))
            if FamilyPerson.objects.filter(family_id=family.id).exists():
                raise FamilyRuleError('FAMILY_NOT_EMPTY', status=409)

            plan = plan_import(body['persons'], body['self_id'])
            id_map = write_import(family, plan, import_key)

        self.family = family
        return self._response(family, id_map, plan.skipped_edges, plan.warnings)

    def _response(self, family, id_map, skipped_edges=(), warnings=()):
        return Response({
            'idMap': id_map,
            'selfId': id_str(family.self_person_id),
            'persons': self.persons(),
            'skippedEdges': list(skipped_edges),
            'warnings': list(warnings),
        })
