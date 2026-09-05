"""Marriage list/create/update/delete.

`order` defaults to `max(existing order for the husband) + 1` when omitted
on create; `order=1` means vợ cả.
"""

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.models import Marriage
from giapha.permissions import IsClanEditor, IsClanMember
from giapha.selectors.marriage import (
    get_marriage_or_none,
    marriages_of,
    next_order_for_husband,
    orders_for_husband,
)
from giapha.selectors.person import get_person_or_none
from giapha.serializers.marriage import MarriageSerializer
from giapha.services.person_rules import PersonValidationError, validate_marriage_distinct, validate_marriage_order_unique

MARRIAGE_NOT_FOUND = 'Không tìm thấy hôn nhân.'
PARTNER_NOT_IN_CLAN = 'Chồng và vợ phải thuộc dòng họ này.'
DUPLICATE_MARRIAGE_DETAIL = 'Cặp vợ chồng này đã tồn tại.'


class MarriageListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        classes = [IsClanMember] if self.request.method in SAFE_METHODS else [IsClanEditor]
        return [IsAuthenticated()] + [cls() for cls in classes]

    def get(self, request, clan_id):
        marriages = marriages_of(clan_id)
        return Response({'data': MarriageSerializer(marriages, many=True).data})

    def post(self, request, clan_id):
        serializer = MarriageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        husband_id, wife_id = data['husband_id'], data['wife_id']
        if get_person_or_none(clan_id, husband_id) is None or get_person_or_none(clan_id, wife_id) is None:
            raise BadRequestException(PARTNER_NOT_IN_CLAN)

        order = data['order'] if data.get('order') is not None else next_order_for_husband(husband_id)
        try:
            validate_marriage_distinct(husband_id, wife_id)
            validate_marriage_order_unique(orders_for_husband(husband_id), order)
        except PersonValidationError as exc:
            raise BadRequestException(str(exc))

        try:
            with transaction.atomic():
                marriage = Marriage.objects.create(
                    husband_id=husband_id, wife_id=wife_id, order=order,
                    status=data['status'], note=data.get('note', ''),
                )
        except IntegrityError:
            # `unique_together = ('husband', 'wife')` -- a second POST for the
            # same pair hits the DB constraint (H5b); surface it as a 400
            # naming the problem instead of letting `IntegrityError` reach
            # the client as a raw 500.
            raise BadRequestException(DUPLICATE_MARRIAGE_DETAIL)
        return Response({'data': MarriageSerializer(marriage).data}, status=status.HTTP_201_CREATED)


class MarriageDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsClanEditor]

    def patch(self, request, clan_id, marriage_id):
        """`husband_id`/`wife_id` are immutable after creation -- accepted
        (and validated) by the serializer if present, but only `order`,
        `status` and `note` are ever applied below. To fix a wrong partner,
        delete and recreate the marriage instead.
        """
        marriage = get_marriage_or_none(clan_id, marriage_id)
        if marriage is None:
            raise NotFound(MARRIAGE_NOT_FOUND)

        serializer = MarriageSerializer(marriage, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        if 'order' in data:
            try:
                validate_marriage_order_unique(
                    orders_for_husband(marriage.husband_id, exclude_marriage_id=marriage.id),
                    data['order'],
                )
            except PersonValidationError as exc:
                raise BadRequestException(str(exc))

        with transaction.atomic():
            for field in ('order', 'status', 'note'):
                if field in data:
                    setattr(marriage, field, data[field])
            marriage.save()

        return Response({'data': MarriageSerializer(marriage).data})

    def delete(self, request, clan_id, marriage_id):
        marriage = get_marriage_or_none(clan_id, marriage_id)
        if marriage is None:
            raise NotFound(MARRIAGE_NOT_FOUND)
        marriage.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
