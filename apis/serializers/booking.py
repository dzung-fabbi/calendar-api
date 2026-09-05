"""Serializers for bookings, reminders and payment details."""

from rest_framework import serializers

from apis.models import AppointmentDate, BankConfig, BookCalendar


class BookCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookCalendar
        fields = ['work', 'date', 'email']


class AppointmentDateSerializer(serializers.ModelSerializer):
    convert_time = serializers.SerializerMethodField('convert_duration')

    def convert_duration(self, data):
        return data.before_days

    class Meta:
        model = AppointmentDate
        fields = ('id', 'name', 'date', 'before_days', 'user_id', 'convert_time')


class BankSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankConfig
        fields = '__all__'
