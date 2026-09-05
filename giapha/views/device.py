"""`POST`/`DELETE /devices` -- register or forget one FCM device token.

`IsAuthenticated` ONLY, never `IsClanMember`. Two reasons, one practical and
one structural:

* `permissions._role_for` reads `view.kwargs['clan_id']`, which this route
  does not have, so `IsClanMember` here would resolve `None` and answer 404
  to every caller;
* a device token belongs to a person's phone, not to a họ. A user in three
  clans registers once and receives reminders from all three.

`token` is a credential: it is accepted in the body, never returned in a
response, and never rendered into a log line (see `DeviceToken.__str__`).

ACCEPTED RISK -- TOKEN TAKEOVER (recorded decision, phase 6 spec line 230):
the upsert is keyed on `token` alone, so whoever presents a token OWNS it
from that moment. That is required for the shared-handset / re-login case,
but it also means anyone who learns another user's FCM token can `POST` it
and redirect that handset's reminders to their own clan. The read direction
stays safe (no endpoint ever returns a token), the write is authenticated,
and the trade-off was chosen deliberately -- it is not an oversight to
"fix" later without revisiting the spec.
"""

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.models import DeviceToken
from giapha.serializers.device import (
    DeviceTokenDeleteSerializer,
    DeviceTokenRegisterSerializer,
)

REGISTER_CONFLICT = 'Không thể đăng ký thiết bị, vui lòng thử lại.'


class DeviceTokenAPIView(APIView):
    """`POST` upserts the token; `DELETE` forgets it (logout)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DeviceTokenRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            # `transaction.atomic()` is what makes the `except` below SAFE: a
            # failed statement poisons its transaction, so without a savepoint
            # the 400 would leave the connection unable to run another query
            # (a guaranteed 500 the day `ATOMIC_REQUESTS` is switched on).
            # Same pattern as `remind_death_anniversary._log`.
            with transaction.atomic():
                # Keyed on `token`, not on `(user, token)`: FCM hands the same
                # token to whoever is logged in on that handset, so a second
                # account registering it must TAKE it over. Leaving the row with
                # the previous owner would push one family's giỗ to another's
                # phone -- the one failure mode worth designing against here.
                device, created = DeviceToken.objects.update_or_create(
                    token=serializer.validated_data['token'],
                    defaults={
                        'user': request.user,
                        'platform': serializer.validated_data['platform'],
                        # A re-registered token is alive again, whatever a
                        # previous failed send concluded.
                        'is_active': True,
                    },
                )
        except IntegrityError:
            # Only reachable if two requests race on the same new token; the
            # unique index is the guard, this keeps it a 400 rather than a 500.
            raise BadRequestException(REGISTER_CONFLICT)

        return Response(
            {'data': {'platform': device.platform, 'is_active': device.is_active}},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request):
        serializer = DeviceTokenDeleteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Filtered by `request.user` so one account cannot unregister
        # another's device, and 204 either way so the response never reveals
        # whether a token exists or who owns it.
        DeviceToken.objects.filter(
            user=request.user, token=serializer.validated_data['token'],
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
