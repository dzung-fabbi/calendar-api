"""Output shape for `GET /tree`.

`selectors.tree.tree_payload()` already returns plain dicts matching the
exact response shape (nodes are deliberately lean -- see phase-04 spec).
`TreeNodeSerializer` used to re-declare every node field and let DRF coerce
each one, which measured as ~57-59% of total `/tree` latency at 1,000-5,000
persons (see `plans/reports/tester-260905-1611-tree-performance-benchmark.md`)
for zero behavior change over just returning the dict: `node_from_row` had
already produced the correct types. It is now a passthrough (`to_representation`
returns the dict unchanged, no re-projection of keys -- rebuilding a new dict
would still be an O(n x fields) pass, defeating the point).

The node shape contract this serializer used to hold now lives in
`services.tree.NODE_FIELDS` + `node_from_row`, guarded by
`tests/test_tree_service.py`'s key-set assertion. This is safe to do here,
UNLIKE the no-auth public surface: `/clans/{id}/tree` requires
`IsClanMember`, so there is no whitelist-by-omission risk the way there would
be on `serializers/public.py` (see that module's docstring, and
`PublicTreeEdgeSerializer`'s, for the incident that shape leaked `parent_kind`
through a passthrough on the public tree edges) -- do not copy this pattern
there.
"""

from rest_framework import serializers


class TreeClanSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    ten_ho = serializers.CharField(allow_null=True)


class TreeNodeSerializer(serializers.Serializer):
    """Passthrough -- see module docstring. Shape is `services.tree.NODE_FIELDS`."""

    def to_representation(self, instance):
        return instance


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
