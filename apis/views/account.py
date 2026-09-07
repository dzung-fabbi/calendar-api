"""Site configuration and the authenticated user's own record."""

from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.models import DateConfig, DirectionConfig, HoursConfig, UserProfile
from apis.serializers import (
    DateConfigSerializer,
    DirectionConfigSerializer,
    HoursConfigSerializer,
    UserSerializer,
)
from apis.serializers.profile import ProfileUpdateSerializer

# Split by which table they live on. Everything absent from these two lists is
# unreachable from a request body -- see the note on `update_fields` below.
USER_FIELDS = ('first_name', 'last_name')
PROFILE_FIELDS = ('phone', 'birth_date', 'avatar_url')


class ConfigAPIView(APIView):
    def get(self, request):
        date_config = DateConfig.objects.order_by('-id').first()
        hours_config = HoursConfig.objects.order_by('-id').first()
        direction_config = DirectionConfig.objects.order_by('-id').first()
        return Response({'data': {
            'date_config': DateConfigSerializer(date_config, many=False).data,
            'hours_config': HoursConfigSerializer(hours_config, many=False).data,
            'direction_config': DirectionConfigSerializer(direction_config, many=False).data,
        }})


class UserAPIView(APIView):
    """The caller's own account. Served at both `/api/get-user` (the original
    name, kept for shipped clients) and `/api/me`.

    `email` and `username` are deliberately NOT writable. They are the same
    value here -- the login identity -- and there is no address-verification
    step, so accepting a change would let anyone holding a stolen token
    repoint the account at their own mailbox and then use the password-reset
    flow to lock the real owner out permanently. Both keys are ignored in
    silence on PATCH, matching how the rest of the API treats read-only fields
    on write (`docs/api-reference.md`).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'data': UserSerializer(self._load(request.user.pk)).data})

    def patch(self, request):
        serializer = ProfileUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        with transaction.atomic():
            user = request.user
            # `get_or_create`, not `user.profile`: accounts older than
            # migration 0055 have no row, because the creating signal only
            # fires on insert (`apis/models/booking.py`).
            profile, _ = UserProfile.objects.get_or_create(user=user)
            self._apply(user, USER_FIELDS, data)
            self._apply(profile, PROFILE_FIELDS, data)

        return Response({'data': UserSerializer(self._load(user.pk)).data})

    @staticmethod
    def _load(pk):
        # `select_related` keeps nesting `profile` at one query, so the ceiling
        # in `test_query_counts.py` does not move.
        return User.objects.select_related('profile').get(pk=pk)

    @staticmethod
    def _apply(instance, names, data):
        """Assign only the whitelisted keys the request actually sent.

        Every field is optional and this is a PATCH, so an ABSENT key must
        leave the stored value alone -- which is why membership in `data` is
        the test, not truthiness (`phone: ""` legitimately clears the field).

        `update_fields` is the second half of the mass-assignment guard: even
        if something upstream mutated the instance, `password`, `is_staff`,
        `is_superuser`, `is_active`, `is_free` and `expiry_datetime` are not in
        the UPDATE statement at all.
        """
        present = [name for name in names if name in data]
        if not present:
            return
        for name in present:
            setattr(instance, name, data[name])
        instance.save(update_fields=present)
