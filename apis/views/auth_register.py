"""`POST /api/auth/register` -- create an account.

The email IS the identity: it is stored as `username` as well as `email`, so
the account works with the existing, untouched `POST /auth/token` password
grant with no further step. Accounts are active immediately; there is no
verification email.
"""

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.serializers.account import UserSerializer
from apis.serializers.auth import EMAIL_TAKEN, RegisterSerializer


class RegisterAPIView(APIView):
    permission_classes = [AllowAny]
    # Unauthenticated, so no per-user throttle bucket exists -- see the
    # NUM_PROXIES caveat on DEFAULT_THROTTLE_RATES in djangopj/settings.py.
    throttle_scope = 'auth-register'
    # The default OAuth2 authenticator would reject a stale or malformed
    # bearer header with a 401 before this view ever runs; a caller with an
    # expired token must still be able to register.
    authentication_classes = ()

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            # The savepoint is mandatory, not defensive: a failed INSERT
            # poisons the surrounding transaction, so catching IntegrityError
            # without it turns this intended 400 into a 500 under
            # `TestCase`/ATOMIC_REQUESTS (`docs/code-standards.md` -> Errors).
            with transaction.atomic():
                user = User.objects.create_user(
                    username=data['email'],
                    email=data['email'],
                    password=data['password'],
                    first_name=data.get('first_name', ''),
                    last_name=data.get('last_name', ''),
                )
        except IntegrityError:
            # Two requests raced past the serializer's existence check. The
            # unique index on `auth_user.username` is what actually decides;
            # answer exactly as the serializer would have, so a client cannot
            # tell a race from an ordinary duplicate.
            return Response({'email': [EMAIL_TAKEN]}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'data': UserSerializer(user).data}, status=status.HTTP_201_CREATED)
