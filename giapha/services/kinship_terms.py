"""Vietnamese kinship vocabulary as DATA. No logic lives in this file.

DIALECT: NORTHERN (miền Bắc), and only that
-------------------------------------------
The North is what gia phả documents are overwhelmingly written in, and it is
the variant this table encodes: the elder sibling of either parent is `bác`
regardless of that sibling's gender or of which parent they are the sibling
of, `chú`/`cô` are reserved for the father's YOUNGER brother/sister, and
`cậu`/`dì` for the mother's. Southern and Central usage differs (many places
say `bác` only for men, `cô` for any paternal aunt, `cậu` for any maternal
uncle). Per-region variants are out of scope for the MVP -- adding them means
a second table keyed by region, not edits to this one.

BOTH SIDES DEPEND ON `birth_order`, and that is the whole point. An earlier
version opted the maternal side out of seniority (`cậu` for any brother of
the mother, stored with `elder=None`), which made it the one place a
seniority-bearing word came back `confident: true` with nothing behind it.
The docstring said `bác`; the table said `cậu`. The table was wrong.

KEY SHAPE: `(kind, gap, side, gender, elder)`
---------------------------------------------
- `kind`  : `TRUC` when one of the two people IS the common ancestor (direct
            line), `BANG` when both sit on branches below it (collateral).
- `gap`   : generations B is ABOVE A. Positive = B is older-generation,
            negative = B is younger-generation, 0 = same generation.
- `side`  : `NOI` when A reaches the common ancestor through their father,
            `NGOAI` through their mother, `None` when A *is* the ancestor.
- `gender`: `gioi_tinh` of the person being NAMED (B), or `None` for a term
            that does not depend on it.
- `elder` : True when B's branch is the ELDER of the common ancestor's two
            children, False when younger, `None` for a term that does not
            depend on seniority.

WHY `gap`, NOT THE PLAN'S LITERAL `(da, db)`
--------------------------------------------
The phase plan keys the table on the raw depth pair. Those two numbers
collapse: a father's cousin (`da=3, db=2`) and an uncle (`da=2, db=1`) share
one word, `bác`/`chú`. Keying on the pair would need an unbounded table to
say the same thing, so the pair is reduced to `(kind, gap)` before lookup.

`None` IS A KEY VALUE, NOT A MISSING ONE. An entry stored with `elder=None`
means "seniority is irrelevant here" (e.g. `ông`, two collateral generations
up, where nobody is anybody's elder branch in the address). Entries that DO
depend on seniority -- every `gap == 1` and `gap == 0` row -- are stored only
under True/False, so an unknown `birth_order` finds nothing and falls through
to `AMBIGUOUS_TERMS`. That is the whole point: guessing bác vs chú wrong is
an insult, so the code must be unable to.

THE GUARANTEE IS ABOUT A MISSING `birth_order`, NOT A MISSING GENDER. Where
one word covers both genders -- `bác` at `elder=True`, `em` at `elder=False`
-- the row is stored with `gender=None` and answers confidently, because
hedging there would throw away a certain answer without buying any honesty.

The in-law words live in `kinship_affinal_terms.py`.
"""

NOI = 'noi'
NGOAI = 'ngoai'

TRUC = 'truc'   # trực hệ -- one of the pair is the common ancestor
BANG = 'bang'   # bàng hệ -- collateral

# `reason` values. EVERY ONE IS AN ASCII SLUG, because `reason` is the field
# a client branches on and half of these used to be diacritic Vietnamese
# prose -- a mobile client comparing `== 'không có từ xưng hô thông dụng'`
# is a wire format nobody would choose on purpose. The human wording lives
# in `REASON_LABELS` and reaches the user through `explain`.
#
# `REASON_NO_BLOOD` means "there is no link at all" and travels with
# `confident: True`. `REASON_AFFINAL_NO_TERM` means "there IS a marriage
# link, Vietnamese has no everyday word for it" and travels with
# `confident: False`. They are different findings; do not merge them.
REASON_MISSING_BIRTH_ORDER = 'thieu_birth_order'
REASON_MISSING_GENDER = 'thieu_gioi_tinh'
REASON_NO_BLOOD = 'khong_cung_huyet_thong'
REASON_AFFINAL_NO_TERM = 'khong_co_tu_xung_ho_thong_dung'
REASON_AMBIGUOUS_MARRIAGE = 'nhieu_hon_nhan_ngang_hang'
REASON_SAME_PERSON = 'cung_mot_nguoi'
REASON_OUT_OF_TABLE = 'ngoai_bang_tu_vung'

# Slug -> the words `kinship_explain` puts in front of a reader. Only the
# reasons that can travel with `confident: False` need one; the two confident
# findings get a whole sentence of their own in `kinship_explain`.
REASON_LABELS = {
    REASON_MISSING_BIRTH_ORDER: 'thiếu birth_order',
    REASON_MISSING_GENDER: 'thiếu giới tính',
    REASON_AFFINAL_NO_TERM: 'không có từ xưng hô thông dụng',
    REASON_AMBIGUOUS_MARRIAGE: 'không rõ cuộc hôn nhân nào là hiện tại',
    REASON_OUT_OF_TABLE: 'quan hệ nằm ngoài bảng từ vựng',
}

# Largest gap UPWARDS the table spells out; past it `kinship_lookup` falls
# back to the generic pair below. Downwards the ladder runs one rung deeper
# (`-5` is `chít`), and that entry is found in `TERMS` before this bound is
# ever consulted -- see `resolve_term`, which tries the table first.
MAX_TABLE_GAP = 4
GENERIC_ANCESTOR = 'tổ tiên'
GENERIC_DESCENDANT = 'hậu duệ'

TERMS = {
    # --- Bàng hệ, cùng đời: anh / chị / em ------------------------------
    # Seniority here is the seniority of the two BRANCHES at the common
    # ancestor, not of the two people: `con của bác` is `anh` even when
    # younger in years. That is exactly what `elder` carries.
    (BANG, 0, None, 'nam', True): 'anh',
    (BANG, 0, None, 'nu', True): 'chị',
    (BANG, 0, None, None, False): 'em',

    # --- Bàng hệ, B một đời trên: bác / chú / cô / cậu / dì --------------
    # Anh/chị của BỐ HAY MẸ đều là bác; chú/cô và cậu/dì chỉ dành cho người
    # ít tuổi hơn cha mẹ mình. Cả hai bên đều cần `birth_order`.
    (BANG, 1, NOI, 'nam', True): 'bác',
    (BANG, 1, NOI, 'nu', True): 'bác',      # chị gái của bố cũng là bác (Bắc)
    (BANG, 1, NOI, 'nam', False): 'chú',
    (BANG, 1, NOI, 'nu', False): 'cô',
    (BANG, 1, NGOAI, 'nam', True): 'bác',   # anh trai của mẹ là bác, không phải cậu
    (BANG, 1, NGOAI, 'nu', True): 'bác',
    (BANG, 1, NGOAI, 'nam', False): 'cậu',
    (BANG, 1, NGOAI, 'nu', False): 'dì',
    # `bác` LÀ TỪ KHÔNG PHÂN BIỆT GIỚI khi đã biết là vai trên -- hai dòng
    # ngay trên mỗi bên lưu đúng cùng một từ cho 'nam' lẫn 'nu'. Đã biết
    # `birth_order` thì thiếu giới tính không làm mất câu trả lời chắc chắn,
    # nên không hedge. `_candidate_keys` tra dòng có giới tính trước, nên hai
    # dòng này chỉ với tới khi giới tính thật sự không biết.
    (BANG, 1, NOI, None, True): 'bác',
    (BANG, 1, NGOAI, None, True): 'bác',

    # --- Bàng hệ, B hai đời trở lên trên ---------------------------------
    (BANG, 2, None, 'nam', None): 'ông',
    (BANG, 2, None, 'nu', None): 'bà',
    (BANG, 3, None, None, None): 'cụ',
    (BANG, 4, None, None, None): 'kỵ',

    # --- Bàng hệ, B dưới: cháu / chắt / chút / chít ----------------------
    # ĐỐI ỨNG TỪNG NẤC VỚI THANG ĐI LÊN NGAY TRÊN: ông↔cháu, cụ↔chắt,
    # kỵ↔chút. Cháu của anh trai mình gọi mình là `ông` và mình gọi nó là
    # `cháu` -- gọi `chắt` là phong nó lên một đời, tức sai vai vế. Thang này
    # do đó lệch một nấc so với thang trực hệ bên dưới (con-cháu-chắt-chút-
    # chít đếm từ chính mình), và sự lệch đó là cố ý.
    (BANG, -1, None, None, None): 'cháu',
    (BANG, -2, None, None, None): 'cháu',
    (BANG, -3, None, None, None): 'chắt',
    (BANG, -4, None, None, None): 'chút',
    (BANG, -5, None, None, None): 'chít',

    # --- Trực hệ lên -----------------------------------------------------
    (TRUC, 1, None, 'nam', None): 'bố',
    (TRUC, 1, None, 'nu', None): 'mẹ',
    (TRUC, 2, NOI, 'nam', None): 'ông nội',
    (TRUC, 2, NOI, 'nu', None): 'bà nội',
    (TRUC, 2, NGOAI, 'nam', None): 'ông ngoại',
    (TRUC, 2, NGOAI, 'nu', None): 'bà ngoại',
    (TRUC, 3, None, 'nam', None): 'cụ ông',
    (TRUC, 3, None, 'nu', None): 'cụ bà',
    (TRUC, 4, None, 'nam', None): 'kỵ ông',
    (TRUC, 4, None, 'nu', None): 'kỵ bà',

    # --- Trực hệ xuống. Shifted one step from the collateral ladder: your
    # own child is `con`, your sibling's child is already `cháu`.
    (TRUC, -1, None, None, None): 'con',
    (TRUC, -2, None, None, None): 'cháu',
    (TRUC, -3, None, None, None): 'chắt',
    (TRUC, -4, None, None, None): 'chút',
    (TRUC, -5, None, None, None): 'chít',
}

# `(kind, gap, side, gender, elder)` -> `(hedge_term, reason)`. SAME KEY
# SHAPE AS `TERMS`, so `resolve_term` widens both tables with one generator.
# Reached ONLY when `TERMS` cannot answer because a fact is missing. The
# hedge names every possibility rather than picking one; the
# `confident: false` that travels with it is the signal for the client to
# ask the user for the missing field.
#
# A `None` `side` means "same hedge whichever side", exactly as in `TERMS`.
#
# THE `elder` SLOT EXISTS SO A HEDGE CANNOT CONTRADICT THE ANSWER PRINTED
# BESIDE IT. Without it, a known-elder sibling of unknown gender came back
# `anh/chị/em` while the very same response told the other person to say
# `em` -- two adjacent fields disagreeing about who is senior. A row stored
# under `elder=None` still means "seniority is unknown here"; the True/False
# rows drop the options seniority has already ruled out.
AMBIGUOUS_TERMS = {
    (BANG, 0, None, 'nam', None): ('anh/em', REASON_MISSING_BIRTH_ORDER),
    (BANG, 0, None, 'nu', None): ('chị/em', REASON_MISSING_BIRTH_ORDER),
    (BANG, 0, None, None, None): ('anh/chị/em', REASON_MISSING_GENDER),
    # Biết là nhánh trên, chỉ thiếu giới tính: `em` đã bị loại.
    (BANG, 0, None, None, True): ('anh/chị', REASON_MISSING_GENDER),
    (BANG, 1, NOI, 'nam', None): ('bác/chú', REASON_MISSING_BIRTH_ORDER),
    (BANG, 1, NOI, 'nu', None): ('bác/cô', REASON_MISSING_BIRTH_ORDER),
    (BANG, 1, NOI, None, None): ('bác/chú/cô', REASON_MISSING_GENDER),
    # Biết là vai dưới cha mẹ mình: `bác` đã bị loại.
    (BANG, 1, NOI, None, False): ('chú/cô', REASON_MISSING_GENDER),
    (BANG, 1, NGOAI, 'nam', None): ('bác/cậu', REASON_MISSING_BIRTH_ORDER),
    (BANG, 1, NGOAI, 'nu', None): ('bác/dì', REASON_MISSING_BIRTH_ORDER),
    (BANG, 1, NGOAI, None, None): ('bác/cậu/dì', REASON_MISSING_GENDER),
    (BANG, 1, NGOAI, None, False): ('cậu/dì', REASON_MISSING_GENDER),
}
