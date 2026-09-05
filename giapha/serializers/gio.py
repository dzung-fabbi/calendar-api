"""Output shape for `GET /clans/{clan_id}/lich-gio`.

The view builds plain dicts in exactly this shape (same arrangement as
`serializers/tree.py`); this module is the single place the contract is
declared so a field change touches one file.
"""

from rest_framework import serializers


class GioLunarSerializer(serializers.Serializer):
    """The lunar date actually observed, which is not always the recorded
    death date -- see `adjusted` on the parent.
    """

    day = serializers.IntegerField()
    month = serializers.IntegerField()


class GioItemSerializer(serializers.Serializer):
    person_id = serializers.IntegerField()
    ho_ten = serializers.CharField()
    thuy_hieu = serializers.CharField(allow_blank=True)
    generation = serializers.IntegerField(allow_null=True)
    lunar = GioLunarSerializer()
    lunar_year = serializers.IntegerField()
    solar_date = serializers.DateField()
    can_chi_ngay = serializers.CharField()
    days_until = serializers.IntegerField()
    # True when a day-30 giỗ was pulled back to day 29 because the month runs
    # short this year. Clients should surface a note: the family will notice.
    adjusted = serializers.BooleanField()


class GioListSerializer(serializers.Serializer):
    items = GioItemSerializer(many=True)
    # True when the clan exceeded `MAX_CLAN_PERSONS` and the tail was
    # dropped, mirroring `TreeSerializer`. A client showing a calendar with
    # people silently missing is worse than one showing a warning.
    truncated = serializers.BooleanField()
