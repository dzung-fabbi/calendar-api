"""Input serializers for registration and the password endpoints.

All of these are plain `Serializer`s, not `ModelSerializer`s: they validate a
request body, they do not represent a row. `create`/`update` are therefore not
implemented -- the views own the writes, because each one has to also revoke
tokens or burn a code inside the same transaction.

Every password and code field is `write_only` (`docs/code-standards.md` ->
Serializers: "A credential is write-only").
"""

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apis.services.otp import CODE_LENGTH

EMAIL_TAKEN = 'Email này đã được sử dụng.'
UNSUPPORTED_CHAR = 'Trường này chứa ký tự không được hỗ trợ.'
SAME_AS_CURRENT = 'Mật khẩu mới phải khác mật khẩu hiện tại.'


def reject_non_bmp(value):
    """Reject characters outside the Basic Multilingual Plane (emoji, mostly).

    `docker-compose.yml` starts MySQL with `--character-set-server=utf8`, which
    in MySQL 5.7 is the THREE-byte encoding -- it cannot store a 4-byte
    character at all. Left through, an emoji in a name raises
    `Incorrect string value` at INSERT: a 500 on an unauthenticated endpoint,
    caused by ordinary user input. Rejecting up front turns it into an honest
    400 (`docs/code-standards.md` -> Errors: validate first, let real faults be
    500s). The alternative fix is migrating the server to `utf8mb4`, which is a
    schema-wide change well outside this feature.
    """
    if any(ord(char) > 0xFFFF for char in value or ''):
        raise serializers.ValidationError(UNSUPPORTED_CHAR)
    return value


def _run_password_validators(password, user=None, field=None):
    """Bridge Django's `AUTH_PASSWORD_VALIDATORS` into DRF's error shape.

    Django raises `django.core.exceptions.ValidationError`, which DRF does not
    catch -- left alone it becomes a 500 on every weak password. Re-raising as
    DRF's own exception is what turns it into the 400 the client expects, with
    all of the validators' messages preserved.

    `field` must be given when calling from `validate()`: a bare list raised
    from a cross-field validator lands under `non_field_errors`, so a client
    reading `errors['password']` would show a weak-password rejection as no
    error at all. Field-level validators key the message themselves and pass
    `field=None`.
    """
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        messages = list(exc.messages)
        raise serializers.ValidationError({field: messages} if field else messages)
    return password


class EmailField(serializers.EmailField):
    """Email normalised to lower case, so that `username` is stable.

    Without this, `User@x.com` and `user@x.com` would register as two separate
    accounts while every lookup in `selectors/password_reset.py` uses
    `iexact` and would then find only the first of them.
    """

    def to_internal_value(self, data):
        return super().to_internal_value(data).strip().lower()


class RegisterSerializer(serializers.Serializer):
    email = EmailField(max_length=150)
    password = serializers.CharField(write_only=True, max_length=128)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150, default='')
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150, default='')

    def validate_first_name(self, value):
        return reject_non_bmp(value)

    def validate_last_name(self, value):
        return reject_non_bmp(value)

    def validate_email(self, value):
        # `max_length=150` above matches `auth_user.username`, not
        # `auth_user.email` (254) -- the address becomes the username, so the
        # shorter column is the real limit and rejecting here beats a
        # DataError at INSERT.
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(EMAIL_TAKEN)
        return value

    def validate(self, attrs):
        # Validated in `validate`, not `validate_password`, so that
        # `UserAttributeSimilarityValidator` can see the email and names it is
        # supposed to compare the password against. Field-level validation
        # runs before siblings exist and would silently skip that check.
        candidate = User(
            username=attrs['email'],
            email=attrs['email'],
            first_name=attrs.get('first_name', ''),
            last_name=attrs.get('last_name', ''),
        )
        _run_password_validators(attrs['password'], user=candidate, field='password')
        return attrs


class ForgotPasswordSerializer(serializers.Serializer):
    email = EmailField(max_length=254)


class VerifyOtpSerializer(serializers.Serializer):
    email = EmailField(max_length=254)
    code = serializers.CharField(write_only=True, min_length=CODE_LENGTH, max_length=CODE_LENGTH)


class ResetPasswordSerializer(serializers.Serializer):
    email = EmailField(max_length=254)
    code = serializers.CharField(write_only=True, min_length=CODE_LENGTH, max_length=CODE_LENGTH)
    new_password = serializers.CharField(write_only=True, max_length=128)

    def validate_new_password(self, value):
        # No `user=` here: resolving the account from the email before the code
        # has been checked would make the password validator's behaviour differ
        # between real and unknown addresses -- an enumeration oracle on an
        # unauthenticated endpoint.
        return _run_password_validators(value)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, max_length=128)
    new_password = serializers.CharField(write_only=True, max_length=128)

    def validate_new_password(self, value):
        # The caller is authenticated, so the similarity validator can and
        # should see their account.
        return _run_password_validators(value, user=self.context.get('user'))

    def validate(self, attrs):
        # A no-op "change" leaves the old password valid while telling the user
        # it was replaced -- and it would still revoke every session, so the
        # visible outcome is a pointless forced re-login.
        if attrs['current_password'] == attrs['new_password']:
            raise serializers.ValidationError({'new_password': [SAME_AS_CURRENT]})
        return attrs
