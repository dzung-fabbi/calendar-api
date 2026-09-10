"""Booking, appointment reminders and bank transfer details."""

import random
import string

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.exceptions import BadRequestException
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

        Items with an `id` update that row; items without one create a row;
        rows of the caller absent from the body are deleted. An `id` the caller
        does not own is a 400 for the whole batch, nothing is changed.
        """
        serializer = AppointmentDateSerializer(data=request.data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        # `validated_data` only: `before_days` arrives as a `timedelta` and
        # `date` as a `date`, so nothing below re-parses client input.
        items = serializer.validated_data
        posted_ids = [item['id'] for item in items if item.get('id')]
        if len(posted_ids) != len(set(posted_ids)):
            # Two items naming one row would update the same instance twice,
            # last one winning in silence.
            raise BadRequestException('Một lịch hẹn xuất hiện hai lần trong danh sách.')

        with transaction.atomic():
            self._replace(user, items, set(posted_ids))

        return Response({
            'data': AppointmentDateSerializer(
                AppointmentDate.objects.filter(user=user), many=True
            ).data
        }, status=status.HTTP_201_CREATED)

    @staticmethod
    def _replace(user, items, posted_ids):
        """Apply the posted list inside the caller's transaction.

        The ownership read locks the rows (`select_for_update`) so that a
        second request from the same user cannot delete them between this
        read and the `bulk_update` below, which would otherwise be a silent
        no-op.
        """
        owned = (
            AppointmentDate.objects.select_for_update()
            .filter(user=user, id__in=posted_ids).in_bulk()
            if posted_ids else {}
        )
        # An id that is not the caller's -- deleted, stale, or somebody else's
        # -- used to be dropped in silence while the replace step still ran,
        # so the client lost a row and got a 201 for it. Refuse the batch
        # instead. One message for "missing" and "not yours": a 400 that told
        # them apart would confirm which ids exist.
        unknown = sorted(posted_ids - set(owned))
        if unknown:
            raise BadRequestException(
                'Lịch hẹn không tồn tại hoặc không thuộc bạn: {}'.format(
                    ', '.join(str(pk) for pk in unknown)
                )
            )

        updates = []
        creates = []
        for item in items:
            row = owned.get(item.get('id'))
            if row is not None:
                row.name = item['name']
                row.date = item['date']
                row.before_days = item['before_days']
                updates.append(row)
            else:
                creates.append(AppointmentDate(
                    name=item['name'], date=item['date'],
                    before_days=item['before_days'], user=user,
                ))

        AppointmentDate.objects.filter(user=user).exclude(id__in=list(owned)).delete()
        if updates:
            AppointmentDate.objects.bulk_update(updates, fields=['name', 'date', 'before_days'])
        if creates:
            AppointmentDate.objects.bulk_create(creates)


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
