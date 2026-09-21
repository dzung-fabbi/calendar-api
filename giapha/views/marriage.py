"""Marriage list/create/update/delete.

`order` defaults to `max(existing order for the husband) + 1` when omitted
on create; `order=1` means vợ cả. Writes go through
`selectors.marriage_write` (shared with change-request approval).
"""

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.permissions import IsClanMember
from giapha.permissions_scope import require_marriage_write, require_write
from giapha.selectors.marriage import get_marriage_or_none, marriages_of
from giapha.selectors.marriage_write import apply_marriage_create, apply_marriage_delete, apply_marriage_update
from giapha.serializers.marriage import MarriageSerializer
from giapha.services.person_rules import PersonValidationError

MARRIAGE_NOT_FOUND = 'Không tìm thấy hôn nhân.'


class MarriageListCreateAPIView(APIView):
    """Writes: editor+, or a verified member when at least one partner is in
    their family scope (`permissions_scope`).
    """

    permission_classes = [IsAuthenticated, IsClanMember]

    def get(self, request, clan_id):
        marriages = marriages_of(clan_id)
        return Response({'data': MarriageSerializer(marriages, many=True).data})

    def post(self, request, clan_id):
        serializer = MarriageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        require_marriage_write(request, clan_id, data['husband_id'], data['wife_id'])
        try:
            marriage = apply_marriage_create(clan_id, data)
        except PersonValidationError as exc:
            raise BadRequestException(str(exc))
        return Response({'data': MarriageSerializer(marriage).data}, status=status.HTTP_201_CREATED)


class MarriageDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsClanMember]

    def patch(self, request, clan_id, marriage_id):
        """`husband_id`/`wife_id` are immutable after creation -- accepted
        (and validated) by the serializer if present, but only `order`,
        `status` and `note` are ever applied. To fix a wrong partner, delete
        and recreate the marriage instead.
        """
        marriage = get_marriage_or_none(clan_id, marriage_id)
        if marriage is None:
            raise NotFound(MARRIAGE_NOT_FOUND)
        require_write(request, clan_id, [marriage.husband_id, marriage.wife_id], any_of=True)

        serializer = MarriageSerializer(marriage, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            apply_marriage_update(marriage, serializer.validated_data)
        except PersonValidationError as exc:
            raise BadRequestException(str(exc))
        return Response({'data': MarriageSerializer(marriage).data})

    def delete(self, request, clan_id, marriage_id):
        marriage = get_marriage_or_none(clan_id, marriage_id)
        if marriage is None:
            raise NotFound(MARRIAGE_NOT_FOUND)
        require_write(request, clan_id, [marriage.husband_id, marriage.wife_id], any_of=True)
        apply_marriage_delete(marriage)
        return Response(status=status.HTTP_204_NO_CONTENT)
