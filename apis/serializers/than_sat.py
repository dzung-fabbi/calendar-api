"""Serializers for the yearly and monthly thần sát tables.

The twelve monthly serializers are identical apart from their model, so they
come from one factory instead of twelve copy-pasted class bodies.
"""

from rest_framework import serializers

from apis.models import (
    SaoMonth1,
    SaoMonth2,
    SaoMonth3,
    SaoMonth4,
    SaoMonth5,
    SaoMonth6,
    SaoMonth7,
    SaoMonth8,
    SaoMonth9,
    SaoMonth10,
    SaoMonth11,
    SaoMonth12,
    ThanSatByMonth,
    ThanSatByYear,
    ThanSatByYearSao,
)
from apis.serializers.stars import SaoSerializer


def _sao_month_serializer(model):
    """Build the `{cung_son, sao, direction}` serializer for one month table."""

    class _SaoMonthSerializer(serializers.ModelSerializer):
        sao = SaoSerializer(read_only=True)

        class Meta:
            pass

    _SaoMonthSerializer.Meta.model = model
    _SaoMonthSerializer.Meta.fields = ['cung_son', 'sao', 'direction']
    _SaoMonthSerializer.__name__ = '{}Serializer'.format(model.__name__)
    return _SaoMonthSerializer


SaoMonth1Serializer = _sao_month_serializer(SaoMonth1)
SaoMonth2Serializer = _sao_month_serializer(SaoMonth2)
SaoMonth3Serializer = _sao_month_serializer(SaoMonth3)
SaoMonth4Serializer = _sao_month_serializer(SaoMonth4)
SaoMonth5Serializer = _sao_month_serializer(SaoMonth5)
SaoMonth6Serializer = _sao_month_serializer(SaoMonth6)
SaoMonth7Serializer = _sao_month_serializer(SaoMonth7)
SaoMonth8Serializer = _sao_month_serializer(SaoMonth8)
SaoMonth9Serializer = _sao_month_serializer(SaoMonth9)
SaoMonth10Serializer = _sao_month_serializer(SaoMonth10)
SaoMonth11Serializer = _sao_month_serializer(SaoMonth11)
SaoMonth12Serializer = _sao_month_serializer(SaoMonth12)


class ThanSatYearSaoSerializer(serializers.ModelSerializer):
    sao = SaoSerializer(read_only=True)

    class Meta:
        model = ThanSatByYearSao
        fields = ['cung_son', 'sao', 'direction']


class ThanSatByYearSerializer(serializers.ModelSerializer):
    than_sat_sao = ThanSatYearSaoSerializer(source='thansatbyyearsao_set', read_only=True, many=True)

    class Meta:
        model = ThanSatByYear
        fields = ['year', 'than_sat_sao']


class ThanSatByMonthSerializer(serializers.ModelSerializer):
    month_01 = SaoMonth1Serializer(source='saomonth1_set', read_only=True, many=True)
    month_02 = SaoMonth2Serializer(source='saomonth2_set', read_only=True, many=True)
    month_03 = SaoMonth3Serializer(source='saomonth3_set', read_only=True, many=True)
    month_04 = SaoMonth4Serializer(source='saomonth4_set', read_only=True, many=True)
    month_05 = SaoMonth5Serializer(source='saomonth5_set', read_only=True, many=True)
    month_06 = SaoMonth6Serializer(source='saomonth6_set', read_only=True, many=True)
    month_07 = SaoMonth7Serializer(source='saomonth7_set', read_only=True, many=True)
    month_08 = SaoMonth8Serializer(source='saomonth8_set', read_only=True, many=True)
    month_09 = SaoMonth9Serializer(source='saomonth9_set', read_only=True, many=True)
    month_10 = SaoMonth10Serializer(source='saomonth10_set', read_only=True, many=True)
    month_11 = SaoMonth11Serializer(source='saomonth11_set', read_only=True, many=True)
    month_12 = SaoMonth12Serializer(source='saomonth12_set', read_only=True, many=True)

    class Meta:
        model = ThanSatByMonth
        fields = [
            'month_01',
            'month_02',
            'month_03',
            'month_04',
            'month_05',
            'month_06',
            'month_07',
            'month_08',
            'month_09',
            'month_10',
            'month_11',
            'month_12',
        ]
