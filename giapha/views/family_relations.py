"""`POST /v1/family/relations/*` -- one endpoint per graph mutation (spec §8.3).

The client never sends a graph; each UI action is one call, the server checks
the invariants against the freshly loaded tree and writes atomically. All five
share the same skeleton: validate body -> load graph -> apply -> respond with
the focus person + the whole `persons[]`.
"""

from django.db import transaction

from giapha.selectors.family import load_graph
from giapha.serializers.family_relations import (
    AddRelativeBodySerializer,
    LinkChildBodySerializer,
    LinkSpouseBodySerializer,
    SetParentBodySerializer,
    UnlinkSpouseBodySerializer,
)
from giapha.services.family_draft import finalize_draft
from giapha.views.family_base import FamilyAPIView
# Absolute module import, not `from giapha.views import ...`: this module is
# itself imported while the `giapha.views` package is still initialising.
from giapha.views import family_link_flow as flow  # noqa: E402  (see above)


class _RelationMutationAPIView(FamilyAPIView):
    body_serializer = None

    def post(self, request):
        data = self.validate(self.body_serializer, request.data)
        with transaction.atomic():
            _, _, graph = load_graph(self.family.id)
            focus_id, warning = self.apply(graph, data)
        return self.mutation_response(focus_id, warning)

    def apply(self, graph, data):  # pragma: no cover -- subclasses implement
        raise NotImplementedError


class FamilyAddRelativeAPIView(_RelationMutationAPIView):
    body_serializer = AddRelativeBodySerializer

    def apply(self, graph, data):
        draft = finalize_draft({}, data['person'])
        return flow.add_relative(
            self.family, graph, data['anchor_id'], data['kind'], draft, data.get('other_parent_id'),
        )


class FamilySetParentAPIView(_RelationMutationAPIView):
    body_serializer = SetParentBodySerializer

    def apply(self, graph, data):
        flow.set_parent(graph, data['child_id'], data['slot'], data['parent_id'], data['rel'])
        return data['child_id'], None


class FamilyLinkSpouseAPIView(_RelationMutationAPIView):
    body_serializer = LinkSpouseBodySerializer

    def apply(self, graph, data):
        warning = flow.link_spouse(self.family, graph, data['a_id'], data['b_id'], data['type'])
        return data['a_id'], warning


class FamilyUnlinkSpouseAPIView(_RelationMutationAPIView):
    body_serializer = UnlinkSpouseBodySerializer

    def apply(self, graph, data):
        flow.unlink_spouse(graph, data['a_id'], data['b_id'])
        return data['a_id'], None


class FamilyLinkChildAPIView(_RelationMutationAPIView):
    body_serializer = LinkChildBodySerializer

    def apply(self, graph, data):
        warning = flow.link_child(graph, data['parent_id'], data['child_id'], data.get('other_parent_id'))
        return data['child_id'], warning
