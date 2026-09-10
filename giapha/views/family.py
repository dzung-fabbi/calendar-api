"""`/v1/family` read, person CRUD (info only -- never edges), "tôi", gio-event.

Spec §8.1, §8.2, §8.4, §8.5. Relationship mutations live in
`views/family_relations.py`; the composition they share is
`views/family_link_flow.py`.
"""

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from giapha.selectors.family import get_person_or_none, load_graph
from giapha.selectors.family_write import apply_draft, delete_person, set_gio_event, set_self
from giapha.serializers.family_draft import PersonDraftSerializer
from giapha.serializers.family_relations import GioEventBodySerializer, SelfBodySerializer
from giapha.services.family_draft import finalize_draft
from giapha.services.family_issue import FamilyRuleError, not_found
from giapha.views.family_base import FamilyAPIView, id_str
from giapha.views.family_link_flow import auto_link_by_label, create_person

# What `finalize_draft` needs from the current row to (re)derive the solar
# death date on a partial update.
_DERIVE_FIELDS = ('lunar_death_day', 'lunar_death_month', 'lunar_death_year', 'lunar_leap', 'solar_death_date')


class FamilyRootAPIView(FamilyAPIView):
    """`GET /v1/family` -> `{selfId, persons[]}` -- the whole tree + meta."""

    def get(self, request):
        return Response({'selfId': id_str(self.family.self_person_id), 'persons': self.persons()})


class FamilyPersonCreateAPIView(FamilyAPIView):
    """`POST /v1/family/persons` -- a standalone person, auto-linked to "tôi"
    when the `relationship` label names one edge (spec §4.8 / §8.2)."""

    def post(self, request):
        incoming = self.validate(PersonDraftSerializer, request.data)
        draft = finalize_draft({}, incoming)
        with transaction.atomic():
            _, _, graph = load_graph(self.family.id)
            person = create_person(self.family, graph, draft)
            linked, hint = auto_link_by_label(self.family, graph, person.id, draft.get('relationship'))
        return self.mutation_response(person.id, status=status.HTTP_201_CREATED, linked=linked, hint=hint)


class FamilyPersonDetailAPIView(FamilyAPIView):
    def _person(self, person_id):
        person = get_person_or_none(self.family.id, person_id)
        if person is None:
            raise not_found(person_id)
        return person

    def get(self, request, person_id):
        persons = self.persons()
        return Response({'person': self.find(persons, person_id)})

    def patch(self, request, person_id):
        """Draft fields only. `fatherId`/`motherId`/`spouses` in the body are
        ignored by the serializer -- edges change through `relations/*`."""
        person = self._person(person_id)
        incoming = self.validate(PersonDraftSerializer, request.data, partial=True)
        current = {field: getattr(person, field) for field in _DERIVE_FIELDS}
        draft = finalize_draft(current, incoming)
        with transaction.atomic():
            apply_draft(person, draft)
        return self.mutation_response(person.id)

    def delete(self, request, person_id):
        """Spec §8.4: hard delete, detach, no cascade. The client-side giỗ
        event is untouched (`gioEventId` simply dies with the row)."""
        person = self._person(person_id)
        with transaction.atomic():
            detached = delete_person(person)
        self.family.refresh_from_db(fields=['self_person'])
        return Response({
            'deleted': True,
            'detachedFrom': [id_str(pid) for pid in detached],
            'selfId': id_str(self.family.self_person_id),
        })


class FamilySelfAPIView(FamilyAPIView):
    """`PUT /v1/family/self {personId|null}`. Setting is allowed when nobody
    holds the role, or when re-asserting the current holder; moving it to
    someone else requires clearing first (spec §8.2: no "cướp vai")."""

    def put(self, request):
        data = self.validate(SelfBodySerializer, request.data)
        person_id = data['person_id']
        if person_id is not None:
            if get_person_or_none(self.family.id, person_id) is None:
                raise not_found(person_id)
            current = self.family.self_person_id
            if current is not None and current != person_id:
                raise FamilyRuleError('SELF_ALREADY_SET', person_id=current, other_id=person_id)
        set_self(self.family, person_id)
        return Response({'selfId': id_str(person_id)})


class FamilyGioEventAPIView(FamilyAPIView):
    """`PUT /v1/family/persons/{id}/gio-event {eventId|null}` -- spec §8.5,
    the "gói trong family" variant: events stay on the device, the server
    only remembers which one belongs to this person."""

    def put(self, request, person_id):
        person = get_person_or_none(self.family.id, person_id)
        if person is None:
            raise not_found(person_id)
        data = self.validate(GioEventBodySerializer, request.data)
        set_gio_event(person, data['event_id'])
        return self.mutation_response(person.id)
