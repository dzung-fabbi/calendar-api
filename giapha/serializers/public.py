"""Output shapes for the no-auth public gia phả surface (phase 9).

WHITELIST, NEVER BLACKLIST -- MANDATORY. Every serializer below declares its
`fields` (plain DRF `Serializer` field declarations, not a `ModelSerializer`
`Meta.fields`) as an exhaustive, explicit list. Nothing here subclasses
`serializers.person.PersonReadSerializer` or `serializers.tree.
TreeNodeSerializer` -- inheriting from either would mean a field added to
those internal serializers in the future is exposed publicly by default.
This module never opts into DRF's blanket "every model field" shortcut and
never drops fields from a full model by name -- `tests/test_public_security.
py` scans this file's source for either pattern and fails the build if one
appears. (Deliberately not spelled out literally in THIS docstring, so the
scan itself has something unambiguous to look for in actual code, not in
prose about the rule.)

`services.public_tree.public_node_from_row` and `services.public_person.
public_person_payload` are what actually decide, per row, whether a field
carries a real value or is blanked for a living person; this module only
declares the SHAPE, matching the convention in `serializers/tree.py`.
"""

from rest_framework import serializers


class PublicTreeClanSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    ten_ho = serializers.CharField(allow_null=True)


class PublicTreeNodeSerializer(serializers.Serializer):
    """One node of the public tree -- IDENTICAL shape for a living and a
    dead person. `mo_phan_*` is not declared here, for anyone; there is no
    flag or role that ever puts grave coordinates on the public page.
    """

    id = serializers.IntegerField()
    ho_ten = serializers.CharField()
    ten_huy = serializers.CharField(allow_null=True)
    generation = serializers.IntegerField(allow_null=True)
    branch = serializers.CharField(allow_blank=True)
    is_truong = serializers.BooleanField()
    birth_order = serializers.IntegerField(allow_null=True)
    # NOT itself a leak, given `selectors.public._is_living`'s STRICT
    # predicate (fails closed on a partial death record, see that
    # docstring): once that holds, `is_living` is exactly
    # `death_year is None and death_lunar is None`, i.e. it carries no
    # information the other two fields don't already carry on this same
    # payload. Do not "simplify" this away later without re-checking that
    # invariant still holds -- it depends on `_is_living` staying stricter
    # than `services.tree.node_from_row`'s OR-semantics, not on this
    # serializer.
    is_living = serializers.BooleanField()
    birth_year = serializers.IntegerField(allow_null=True)
    death_year = serializers.IntegerField(allow_null=True)
    death_lunar = serializers.DictField(allow_null=True)
    # Bool only, and always False for a living person -- see
    # `services.public_tree.public_node_from_row`.
    has_photo = serializers.BooleanField()


class PublicTreeEdgeSerializer(serializers.Serializer):
    """Parent edges only -- see `selectors.public.public_tree_payload` for
    why marriages are out of scope at MVP.

    PROJECTS AN EXPLICIT KEY LIST rather than passing the dict straight
    through like `serializers.tree.TreeEdgeSerializer` does. A passthrough
    is a blacklist by omission: it publishes whatever keys the edge builder
    happens to put in the dict, so the whitelist guarantee this module is
    built on -- and the key-set canary tests -- covered `nodes` only and
    left `edges` completely unguarded. That is not hypothetical: parent
    edges carried `kind` (`Person.parent_kind`, i.e. `ruot`/`nuoi`/`ke`),
    which published adoption/step-child status for LIVING people, a field
    nowhere on the phase-9 whitelist table.

    Declared as a key tuple instead of DRF fields because `from` is a
    Python keyword and cannot be a serializer attribute name.
    """

    _ALLOWED_KEYS = ('type', 'from', 'to', 'role')

    def to_representation(self, instance):
        return {key: instance[key] for key in self._ALLOWED_KEYS}


class PublicTreeSerializer(serializers.Serializer):
    clan = PublicTreeClanSerializer()
    nodes = PublicTreeNodeSerializer(many=True)
    edges = PublicTreeEdgeSerializer(many=True)
    truncated = serializers.BooleanField()


class PublicPersonSerializer(serializers.Serializer):
    """`GET /public/{slug}/persons/{pid}`. Richer than the tree node for a
    dead person (biography-shaped fields); for a living one it is exactly
    as lean as the tree node -- `services.public_person.
    public_person_payload` decides which keys carry real values.

    `mo_phan_*` is not declared here either, for anyone.
    """

    id = serializers.IntegerField()
    ho_ten = serializers.CharField()
    ten_huy = serializers.CharField(allow_null=True)
    ten_tu = serializers.CharField(allow_null=True)
    ten_hieu = serializers.CharField(allow_null=True)
    thuy_hieu = serializers.CharField(allow_null=True)
    generation = serializers.IntegerField(allow_null=True)
    branch = serializers.CharField(allow_blank=True)
    is_truong = serializers.BooleanField()
    birth_order = serializers.IntegerField(allow_null=True)
    # See `PublicTreeNodeSerializer.is_living` above -- same invariant,
    # not a leak, and depends on the same `selectors.public._is_living`.
    is_living = serializers.BooleanField()
    birth_year = serializers.IntegerField(allow_null=True)
    death_year = serializers.IntegerField(allow_null=True)
    death_lunar = serializers.DictField(allow_null=True)
    que_quan = serializers.CharField(allow_null=True)
    nghe_nghiep = serializers.CharField(allow_null=True)
    tieu_su = serializers.CharField(allow_null=True)
    # Presigned GET, dead people only -- `services.public_person._photo_url`
    # never mints one for a living person regardless of `hide_living_details`.
    photo_url = serializers.CharField(allow_null=True)
