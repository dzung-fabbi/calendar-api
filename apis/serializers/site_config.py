"""Serializers for the admin-editable rating thresholds."""

from rest_framework import serializers

from apis.models import DateConfig, DirectionConfig, HoursConfig


class DateConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = DateConfig
        fields = '__all__'


class HoursConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = HoursConfig
        fields = '__all__'


class DirectionConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = DirectionConfig
        fields = '__all__'
