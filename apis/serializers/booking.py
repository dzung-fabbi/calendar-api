"""Serializers for bookings, reminders and payment details."""

from datetime import timedelta

from rest_framework import serializers

from apis.models import AppointmentDate, BankConfig, BookCalendar

# A year of lead time is already generous for a vehicle inspection or an
# insurance renewal; anything larger is almost certainly a unit mistake.
MAX_BEFORE_DAYS = 365


class BookCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookCalendar
        fields = ['work', 'date', 'email']


class WholeDaysField(serializers.IntegerField):
    """`AppointmentDate.before_days` as a plain number of days, both ways.

    The column is a `DurationField`. DRF's default field rendered it as
    `"3 00:00:00"` while the view fed the posted value to `int()`, so a client
    that sent back exactly what it had received got a 500. Whole days in, whole
    days out; the view receives a ready `timedelta`.
    """

    default_error_messages = {
        'out_of_range': 'Số ngày nhắc trước phải từ 0 đến {max_days}.',
    }

    def __init__(self, max_days, **kwargs):
        # Not `min_value`/`max_value`: DRF runs those validators on the value
        # `to_internal_value` returns, and a `timedelta` cannot be compared to
        # an int. The range check happens on the integer, below.
        self.max_days = max_days
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        days = super().to_internal_value(data)
        if not 0 <= days <= self.max_days:
            self.fail('out_of_range', max_days=self.max_days)
        return timedelta(days=days)

    def to_representation(self, value):
        return value.days


class AppointmentDateSerializer(serializers.ModelSerializer):
    # Writable so `validated_data` carries it; the view resolves ownership.
    id = serializers.IntegerField(required=False, allow_null=True)
    # The column allows NULL, but a reminder without a date can never fire.
    date = serializers.DateField()
    before_days = WholeDaysField(max_days=MAX_BEFORE_DAYS, default=timedelta)
    # Legacy alias of `before_days` kept for shipped clients; same integer.
    convert_time = serializers.SerializerMethodField()

    def get_convert_time(self, row):
        return row.before_days.days

    class Meta:
        model = AppointmentDate
        fields = ('id', 'name', 'date', 'before_days', 'user_id', 'convert_time')


class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankConfig
        fields = '__all__'
