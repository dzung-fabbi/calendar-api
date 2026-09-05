"""Booking, appointment reminders and bank transfer details."""

import random
import string
from datetime import timedelta

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.models import AppointmentDate, BankConfig, BankTransaction
from apis.serializers import (
    AppointmentDateSerializer,
    BankSerializer,
    BookCalendarSerializer,
)

TRANSACTION_CODE_LENGTH = 6


class BookCalendarAPIView(APIView):
    def post(self, request, format=None):
        serializer = BookCalendarSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AppointmentDateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = AppointmentDate.objects.filter(user_id=request.user.id)
        serializer = AppointmentDateSerializer(data, many=True)
        return Response({'data': serializer.data})

    def post(self, request, format=None):
        """Replace the caller's appointment list with the posted one.

        Every row is scoped to `request.user`. Previously the rows were looked
        up by client-supplied id with no ownership filter, and the owner was
        then read back off the fetched row -- so posting somebody else's id was
        enough to read, overwrite and delete their appointments. Creates also
        went through `AppointmentDate(**data)`, which let the caller set the
        `user` column directly.
        """
        serializer = AppointmentDateSerializer(data=request.data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        posted_ids = [item['id'] for item in request.data if item.get('id')]

        # One query for every row being updated, restricted to the owner.
        owned = AppointmentDate.objects.in_bulk(posted_ids) if posted_ids else {}
        owned = {pk: row for pk, row in owned.items() if row.user_id == user.id}

        updates = []
        creates = []
        for item in request.data:
            item_id = item.get('id')
            row = owned.get(item_id) if item_id else None
            if row is not None:
                row.name = item.get('name', None)
                row.date = item.get('date', None)
                row.before_days = timedelta(days=int(item.get('before_days', 0)))
                updates.append(row)
            elif not item_id:
                creates.append(AppointmentDate(
                    name=item.get('name', None),
                    date=item.get('date', None),
                    before_days=timedelta(days=int(item.get('before_days', 0))),
                    user=user,
                ))

        with transaction.atomic():
            AppointmentDate.objects.filter(user=user).exclude(
                id__in=list(owned)
            ).delete()
            if updates:
                AppointmentDate.objects.bulk_update(
                    updates, fields=['name', 'date', 'before_days']
                )
            if creates:
                AppointmentDate.objects.bulk_create(creates)

        return Response({
            'data': AppointmentDateSerializer(
                AppointmentDate.objects.filter(user=user), many=True
            ).data
        }, status=status.HTTP_201_CREATED)


class BankAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        bank = BankConfig.objects.first()

        # get_or_create instead of check-then-insert: two concurrent calls from
        # the same user used to be able to open two open transactions, each
        # with a different payment reference.
        pending, _created = BankTransaction.objects.get_or_create(
            user=user,
            status=0,
            defaults={'code': self._new_code()},
        )
        return Response({'data': {
            'bank': BankSerializer(bank, many=False).data,
            'code': pending.code,
        }})

    @staticmethod
    def _new_code():
        return ''.join(
            random.choices(string.ascii_uppercase, k=TRANSACTION_CODE_LENGTH)
        )
