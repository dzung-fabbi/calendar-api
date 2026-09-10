"""Base view for `/v1/family/*`.

Every endpoint here is scoped to the caller's OWN family (spec §8: "mọi
resource thuộc gia phả của user đó") -- there is no clan/role layer, just
`IsAuthenticated`. `initial()` resolves (or lazily creates) that family so a
brand-new user's first `GET /v1/family` returns an empty tree, not a 404.

Responses are FLAT (no `{"data": ...}` wrapper) because the spec fixes their
shape; errors are the spec's envelope, produced from `FamilyRuleError` in
`handle_exception` so rule code never has to know about HTTP.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.selectors.family import family_for, person_rows, spouse_rows
from giapha.serializers.family_output import id_str, persons_payload
from giapha.services.family_issue import FamilyRuleError, not_found


def first_error_message(errors):
    """The first human-readable string inside a DRF `errors` structure --
    what the app shows as a toast; the full structure rides along as `fields`."""
    if isinstance(errors, dict):
        for value in errors.values():
            found = first_error_message(value)
            if found:
                return found
    elif isinstance(errors, (list, tuple)):
        for value in errors:
            found = first_error_message(value)
            if found:
                return found
    elif errors:
        return str(errors)
    return None


class FamilyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.family = family_for(request.user)

    def handle_exception(self, exc):
        if isinstance(exc, FamilyRuleError):
            return Response({'ok': False, 'error': exc.to_error()}, status=exc.status)
        return super().handle_exception(exc)

    @staticmethod
    def validate(serializer_class, data, **kwargs):
        """`validated_data` or a `VALIDATION` rule error carrying the field
        errors -- so shape errors use the same envelope as rule errors."""
        serializer = serializer_class(data=data, **kwargs)
        if not serializer.is_valid():
            raise FamilyRuleError(
                'VALIDATION', message=first_error_message(serializer.errors),
                extra={'fields': serializer.errors},
            )
        return serializer.validated_data

    def persons(self):
        """Fresh `persons[]` after any write -- two queries, whole family."""
        return persons_payload(person_rows(self.family.id), spouse_rows(self.family.id))

    @staticmethod
    def find(persons, person_id):
        wanted = id_str(person_id)
        for person in persons:
            if person['id'] == wanted:
                return person
        raise not_found(person_id)

    def mutation_response(self, focus_id, warning=None, status=200, **extra):
        """Spec §8.3 success envelope: the person the call was about plus the
        whole (small) tree, so the client can replace its local list."""
        persons = self.persons()
        body = {'ok': True, 'person': self.find(persons, focus_id), 'persons': persons, 'warning': warning}
        body.update(extra)
        return Response(body, status=status)
