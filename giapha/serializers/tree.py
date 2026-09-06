"""Output shape for `GET /tree`.

`selectors.tree.tree_payload()` already returns plain dicts matching this
exact shape (nodes are deliberately lean -- see phase-04 spec); this
serializer's only job is to be the one place that shape is declared, so a
future field addition/removal touches one file.
"""

from rest_framework import serializers


class TreeClanSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    ten_ho = serializers.CharField(allow_null=True)


class TreeNodeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    ho_ten = serializers.CharField()
    ten_huy = serializers.CharField(allow_blank=True)
    gioi_tinh = serializers.CharField()
    generation = serializers.IntegerField(allow_null=True)
    branch = serializers.CharField(allow_blank=True)
    is_truong = serializers.BooleanField()
    birth_order = serializers.IntegerField(allow_null=True)
    is_living = serializers.BooleanField()
    birth_year = serializers.IntegerField(allow_null=True)
    death_year = serializers.IntegerField(allow_null=True)
    death_lunar = serializers.DictField(allow_null=True)
    # Bool only, never a presigned URL -- see `services.tree.node_from_row`
    # and the phase-08 spec ("cây chỉ trả has_photo").
    has_photo = serializers.BooleanField()


class TreeEdgeSerializer(serializers.Serializer):
    """Deliberately a passthrough: a `parent` edge and a `marriage` edge have
    different keys (`from`/`to`/`role`/`kind` vs `a`/`b`/`order`/`status`),
    with `type` as the client's discriminator between them. The dicts built
    by `services.tree.parent_edges_from_rows`/`marriage_edges_from_rows` are
    already exactly this shape.
    """

    def to_representation(self, instance):
        return instance


class TreeSerializer(serializers.Serializer):
    clan = TreeClanSerializer()
    nodes = TreeNodeSerializer(many=True)
    edges = TreeEdgeSerializer(many=True)
    truncated = serializers.BooleanField()
