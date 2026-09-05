"""Shapes for `POST/DELETE /devices`.

`token` is a credential. It is accepted here and nowhere else, and never
echoed back in a response -- see `views/device.py`.
"""

from rest_framework import serializers

from giapha.models import DEVICE_PLATFORM


class DeviceTokenRegisterSerializer(serializers.Serializer):
    """`POST /devices` body.

    Plain `Serializer`, not a `ModelSerializer`: the row is an upsert keyed
    by `token` and owned by `request.user`, so a model-bound serializer would
    only invite `user` to become a writable field.
    """

    token = serializers.CharField(max_length=255)
    platform = serializers.ChoiceField(choices=DEVICE_PLATFORM)


class DeviceTokenDeleteSerializer(serializers.Serializer):
    """`DELETE /devices` body -- logout of one device."""

    token = serializers.CharField(max_length=255)
