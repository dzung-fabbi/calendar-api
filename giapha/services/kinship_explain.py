"""The human-readable `explain` string of the xưng-hô answer.

Split out of `services/kinship.py` so the algorithm file stays about the
algorithm. Pure string assembly -- it is handed names and numbers that the
caller has already resolved, and invents nothing.

EVERY SENTENCE ONLY RESTATES FACTS THE CALLER PASSED IN. There is no
"bác là anh trai của bố bạn" here, however nice that reads: it would assert
a gender and a seniority that the term itself may only be hedging at. When
`confident` is False the sentence says which field is missing instead.
"""

from giapha.services.kinship_terms import (
    REASON_LABELS,
    REASON_NO_BLOOD,
    REASON_SAME_PERSON,
)

UNKNOWN_TERM = 'không xác định được'

SIDE_LABELS = {'noi': ', bên nội', 'ngoai': ', bên ngoại'}

NONE_SENTENCES = {
    REASON_SAME_PERSON: 'Hai mã số cùng trỏ về một người.',
    REASON_NO_BLOOD: 'Không tìm thấy tổ tiên chung giữa hai người trong dòng họ này.',
}


def _term_text(entry):
    return entry.get('term') or UNKNOWN_TERM


def _doubts(*entries):
    """The distinct `reason`s of the entries that are not confident, joined.

    `reason` IS A SLUG ON THE WIRE and Vietnamese in here: `REASON_LABELS`
    is the one place the two meet, so a client branching on the field never
    has to compare a diacritic string. An unmapped slug falls back to itself
    rather than disappearing from the sentence.

    Order is preserved rather than sorted so the caller's own order (A then
    B) is what the reader sees.
    """
    reasons = []
    for entry in entries:
        reason = REASON_LABELS.get(entry.get('reason'), entry.get('reason'))
        if not entry.get('confident') and reason and reason not in reasons:
            reasons.append(reason)
    if not reasons:
        return ''
    return ' Chưa chắc chắn do {}.'.format(', '.join(reasons))


def explain_blood(name_a, name_b, a_calls_b, b_calls_a, ancestor_name, depth_a, depth_b, side):
    return (
        '{a} gọi {b} là {t1}; {b} gọi {a} là {t2}. '
        'Tổ tiên chung: {anc} ({a} cách {da} đời, {b} cách {db} đời{side}).{doubt}'
    ).format(
        a=name_a, b=name_b,
        t1=_term_text(a_calls_b), t2=_term_text(b_calls_a),
        anc=ancestor_name, da=depth_a, db=depth_b,
        side=SIDE_LABELS.get(side, ''),
        doubt=_doubts(a_calls_b, b_calls_a),
    )


def explain_affinal(name_a, name_b, spouse_name, spouse_term, *entries):
    """`spouse_name is None` means A and B are married to each other; that is
    the one case with no third person and no common ancestor to name.

    `entries` are the two answer dicts, so a hedged in-law term says which
    field is missing exactly as a hedged blood term does -- the module
    promises that above, and this branch used not to keep the promise.
    """
    if spouse_name is None:
        return '{a} và {b} là vợ chồng.{doubt}'.format(
            a=name_a, b=name_b, doubt=_doubts(*entries),
        )
    return (
        '{b} kết hôn với {s}. {a} gọi {s} là {t}, nên xưng hô với {b} '
        'theo quan hệ hôn nhân đó.{doubt}'
    ).format(
        a=name_a, b=name_b, s=spouse_name, t=spouse_term or UNKNOWN_TERM,
        doubt=_doubts(*entries),
    )


def explain_affinal_mirrored(
    name_married, name_relative, spouse_name, spouse_term, own_term, *entries,
):
    """The sentence for the direction where A is the one who married in.

    `explain_affinal` above is written from the blood relative's side, and
    reusing it here printed a sentence that justified `b_calls_a` while the
    client was reading `a_calls_b` -- "Bo gọi Chong là con" next to a
    displayed term of `bố`. Every clause was true and none of them was about
    the word on screen.

    BOTH WORDS APPEAR because they are not always the same one: the spouse
    may say `ông nội` where the person who married in says `ông` (see
    `MARRIED_IN_SUBSTITUTES`). Printing only the borrowed word would put a
    blood claim in the sentence that the answer itself refuses to make.
    """
    return (
        '{a} kết hôn với {s}. {s} gọi {b} là {t0}, nên {a} gọi {b} là '
        '{t1}.{doubt}'
    ).format(
        a=name_married, b=name_relative, s=spouse_name,
        t0=spouse_term or UNKNOWN_TERM, t1=own_term or UNKNOWN_TERM,
        doubt=_doubts(*entries),
    )


def explain_none(reason):
    return NONE_SENTENCES.get(
        reason, 'Không xác định được quan hệ giữa hai người.'
    )
