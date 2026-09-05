"""Shape for `GET /clans/{id}/xung-ho`.

Describes the plain dict `services.kinship.resolve_kinship` returns, not a
model instance -- same arrangement as `serializers/gio.py`. There is no row
to serialise: the answer is computed.

EVERYTHING NULLABLE IS NULLABLE ON PURPOSE. `term` is null when no word
applies, and `common_ancestor` is null whenever the answer did not come from
a blood walk -- two strangers, the same person twice, a married couple, or
ANY in-law answer. A client must render `term: null` as "no word for this",
not as an error: the response is a 200 (plan step 6), and `confident` plus
`reason` say which kind of "no word" it is.

`path` IS THE EXCEPTION -- it is ALWAYS an object, never null, because the
field is declared without `allow_null` and every non-blood answer passes
`EMPTY_PATH`. So a client reads `path.a_up` / `path.b_up` / `path.side` as
three independently nullable values and must not test `path` itself for
null. Kept this way so the shape does not change between answer kinds.
"""

from rest_framework import serializers

from giapha.services.kinship_terms import NGOAI, NOI

KINSHIP_SIDE = (
    (NOI, 'Bên nội'),
    (NGOAI, 'Bên ngoại'),
)


class KinshipTermSerializer(serializers.Serializer):
    """One direction of the pair.

    `confident: false` means a fact was missing and `term` is a hedge naming
    every possibility still open (`bác/chú`), with `reason` saying what to
    fill in. It is a prompt to improve the data, not an error to hide --
    clans entered without `birth_order` will see a lot of it. The hedge only
    ever lists options the KNOWN facts leave open, so it never contradicts
    the term travelling in the other direction of the same answer.

    `reason` IS A MACHINE-READABLE ASCII SLUG, always -- it is the field a
    client branches on, and half of these used to be diacritic Vietnamese
    prose that a mobile client would have had to compare verbatim. The
    values, all from `services.kinship_terms`:

        khong_cung_huyet_thong          no link at all (`confident: true`)
        cung_mot_nguoi                  the two ids are the same person
        thieu_birth_order               fill in `birth_order` to be sure
        thieu_gioi_tinh                 fill in `gioi_tinh` to be sure
        khong_co_tu_xung_ho_thong_dung  a marriage link with no everyday word
        nhieu_hon_nhan_ngang_hang       two marriages the data ranks equally
        ngoai_bang_tu_vung              outside the vocabulary table

    The Vietnamese wording for each is in `REASON_LABELS` and reaches the
    user through `explain`; do not render `reason` itself.
    """

    term = serializers.CharField(allow_null=True)
    confident = serializers.BooleanField()
    reason = serializers.CharField(allow_null=True)


class KinshipPersonSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    ho_ten = serializers.CharField()


class KinshipPathSerializer(serializers.Serializer):
    """Generations up from each person to the common ancestor, and which of
    A's parents the walk started through. Enough for a client to draw the
    path or to explain the answer in its own words.

    ALL THREE ARE NULL ON AN IN-LAW ANSWER, and drawing nothing is the point:
    there the only walk that exists runs between A and B's SPOUSE, so `b_up`
    would count generations for someone who is not descended from that
    ancestor at all. `explain` names the spouse instead.
    """

    a_up = serializers.IntegerField(allow_null=True)
    b_up = serializers.IntegerField(allow_null=True)
    side = serializers.ChoiceField(choices=KINSHIP_SIDE, allow_null=True)


class KinshipSerializer(serializers.Serializer):
    a_calls_b = KinshipTermSerializer()
    b_calls_a = KinshipTermSerializer()
    common_ancestor = KinshipPersonSerializer(allow_null=True)
    path = KinshipPathSerializer()
    explain = serializers.CharField()
