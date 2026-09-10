"""`PersonDraft` input (spec §3.1 / §8.2): every Person field EXCEPT `id`,
`createdAt`, `updatedAt`, `fatherId`, `motherId`, `fatherRel`, `motherRel`,
`spouses`. Relationship edges never travel in a draft -- a client that sends
`fatherId` here has it silently ignored (DRF drops unknown keys), which is
what "PATCH person không đổi được fatherId / spouses" (spec §13) requires.

Wire names are camelCase; `source=` maps each onto the snake_case model
field so `validated_data` is directly writable.
"""

from rest_framework import serializers

from giapha.models import FAMILY_GENDER
from giapha.services.family_dates import DATE_FORMAT, TIME_PATTERN

_TIME_ERROR = 'Giờ phải theo định dạng HH:mm (24 giờ).'


def _text(max_length, source=None):
    # `source` only when the wire name differs from the model field -- DRF
    # asserts against a redundant `source='relationship'` on `relationship`.
    kwargs = {'source': source} if source else {}
    return serializers.CharField(
        max_length=max_length, required=False, allow_null=True, allow_blank=True, **kwargs,
    )


def _time(source):
    return serializers.RegexField(
        TIME_PATTERN, source=source, required=False, allow_null=True, allow_blank=True,
        error_messages={'invalid': _TIME_ERROR},
    )


def _date(source):
    return serializers.DateField(
        source=source, input_formats=[DATE_FORMAT], format=DATE_FORMAT, required=False, allow_null=True,
        error_messages={'invalid': 'Ngày phải theo định dạng DD-MM-YYYY.'},
    )


class PersonDraftSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=60, trim_whitespace=True,
        error_messages={'blank': 'Tên không được để trống.', 'required': 'Tên là bắt buộc.',
                        'max_length': 'Tên tối đa 60 ký tự.'},
    )
    gender = serializers.ChoiceField(choices=[value for value, _ in FAMILY_GENDER], default='unknown')
    deceased = serializers.BooleanField(default=False)

    solarBirthDate = _date('solar_birth_date')
    birthTime = _time('birth_time')
    birthOrder = serializers.IntegerField(source='birth_order', min_value=1, required=False, allow_null=True)

    solarDeathDate = _date('solar_death_date')
    deathTime = _time('death_time')
    lunarDeathDay = serializers.IntegerField(
        source='lunar_death_day', min_value=1, max_value=30, required=False, allow_null=True,
        error_messages={'min_value': 'Ngày mất âm lịch phải trong khoảng 1-30.',
                        'max_value': 'Ngày mất âm lịch phải trong khoảng 1-30.'},
    )
    lunarDeathMonth = serializers.IntegerField(
        source='lunar_death_month', min_value=1, max_value=12, required=False, allow_null=True,
        error_messages={'min_value': 'Tháng mất âm lịch phải trong khoảng 1-12.',
                        'max_value': 'Tháng mất âm lịch phải trong khoảng 1-12.'},
    )
    lunarDeathYear = serializers.IntegerField(source='lunar_death_year', required=False, allow_null=True)
    lunarLeap = serializers.BooleanField(source='lunar_leap', required=False, allow_null=True)

    relationship = _text(24)
    note = _text(200)
    gioEventId = _text(64, source='gio_event_id')
