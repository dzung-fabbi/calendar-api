"""Star serialization, plus the payload helper the almanac serializers share."""

from rest_framework import serializers

from apis.models import Sao


def star_payload(rows):
    """Render through-table rows (each with a `.sao`) as the API's star dicts.

    Reads `row.sao` directly, so callers should hand in a queryset that was
    fetched with `select_related('sao')` -- otherwise this is an N+1.
    """
    return [
        {
            "name": row.sao.name,
            "property": row.sao.property,
            "good_ugly_stars": row.sao.good_ugly_stars,
        }
        for row in rows
    ]


def named_star_payload(rows):
    """The narrower shape used by HiepKy, which omits `good_ugly_stars`."""
    return [
        {
            "name": row.sao.name,
            "property": row.sao.property,
        }
        for row in rows
    ]


class SaoSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()

    class Meta:
        model = Sao
        fields = [
            'id',
            'name',
            'property',
            'good_ugly_stars',
            'is_mountain',
            'category',
            'calendar',
            'level',
            'level_year',
            'level_month',
            'level_day',
            'level_hours',
            'point',
        ]

    def get_category(self, obj):
        if obj.category is None:
            return None
        return {
            "id": obj.category.id,
            "name": obj.category.name,
        }
