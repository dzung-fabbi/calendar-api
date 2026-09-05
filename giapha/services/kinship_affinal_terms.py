"""In-law (bên dâu/rể) vocabulary as DATA. No logic lives in this file.

Split from `kinship_terms.py` to keep both files under the 200-line house
rule; that file holds the blood words, this one the words a marriage edge
produces. Same dialect, same "None is a key, not a gap" discipline.

DIALECT: NORTHERN, as in `kinship_terms.py`. Read that docstring first.
"""

# `(term A uses for the blood relative, gender of that relative's spouse)`
# -> term A uses for the spouse. Marriage does not create a new generation,
# so the affinal word is simply the blood word restated for the in-law.
# Hedges are carried through as hedges rather than dropped -- "bác gái/thím"
# is still more use than silence, and `confident` stays False either way.
#
# A MISS IS NOT "NO RELATION". `services.kinship` answers a miss with
# `REASON_AFFINAL_NO_TERM` and `confident: False`, naming the spouse it went
# through, because "there is a link and I have no word for it" and "there is
# no link" are different things to tell a user. Rows are therefore added only
# where the everyday word is not in doubt: a stepmother (`('bố', 'nu')`) is
# deliberately absent because usage genuinely varies (mẹ / dì / mẹ kế) and
# guessing between them is exactly the insult this module exists to avoid.
#
# `bác gái` rather than `bác` for the wife of a `bác`: it is the ordinary
# Northern word and it distinguishes her from the blood `bác` in the same
# sentence. Identical on the paternal and maternal side, so the single key
# `('bác', 'nu')` covers both.
AFFINAL_TERMS = {
    ('chú', 'nu'): 'thím',
    ('cậu', 'nu'): 'mợ',
    ('cô', 'nam'): 'chú',
    ('dì', 'nam'): 'dượng',
    ('bác', 'nam'): 'bác',
    ('bác', 'nu'): 'bác gái',
    ('anh', 'nu'): 'chị',
    ('chị', 'nam'): 'anh',
    ('em', 'nam'): 'em',
    ('em', 'nu'): 'em',
    ('con', 'nam'): 'con',
    ('con', 'nu'): 'con',
    ('cháu', 'nam'): 'cháu',
    ('cháu', 'nu'): 'cháu',
    ('chắt', 'nam'): 'chắt',
    ('chắt', 'nu'): 'chắt',
    ('chút', 'nam'): 'chút',
    ('chút', 'nu'): 'chút',
    ('chít', 'nam'): 'chít',
    ('chít', 'nu'): 'chít',
    ('ông', 'nu'): 'bà',
    ('bà', 'nam'): 'ông',
    ('cụ', 'nam'): 'cụ',
    ('cụ', 'nu'): 'cụ',
    ('kỵ', 'nam'): 'kỵ',
    ('kỵ', 'nu'): 'kỵ',
    # Vợ sau của ông, chồng sau của bà: vẫn gọi là ông/bà, nhưng không phải
    # `ông nội`/`bà ngoại` -- những từ đó hàm ý huyết thống. Chiều ngược lại
    # theo đúng luật ấy qua `MARRIED_IN_SUBSTITUTES` bên dưới.
    ('ông nội', 'nu'): 'bà',
    ('bà nội', 'nam'): 'ông',
    ('ông ngoại', 'nu'): 'bà',
    ('bà ngoại', 'nam'): 'ông',
    ('cụ ông', 'nu'): 'cụ',
    ('cụ bà', 'nam'): 'cụ',
    ('kỵ ông', 'nu'): 'kỵ',
    ('kỵ bà', 'nam'): 'kỵ',
    # Cờ nghi ngờ đi tiếp thành cờ nghi ngờ, không được biến mất.
    ('bác/chú', 'nu'): 'bác gái/thím',
    ('bác/cô', 'nam'): 'bác/chú',
    ('bác/chú/cô', 'nam'): 'bác/chú',
    ('bác/chú/cô', 'nu'): 'bác gái/thím',
    ('bác/cậu', 'nu'): 'bác gái/mợ',
    ('bác/dì', 'nam'): 'bác/dượng',
    ('bác/cậu/dì', 'nam'): 'bác/dượng',
    ('bác/cậu/dì', 'nu'): 'bác gái/mợ',
    ('anh/em', 'nu'): 'chị/em',
    ('chị/em', 'nam'): 'anh/em',
    ('anh/chị/em', 'nam'): 'anh/em',
    ('anh/chị/em', 'nu'): 'chị/em',
    # Hedge hẹp hơn, sinh ra khi đã biết thứ bậc mà chưa biết giới tính.
    # Giới tính của NGƯỜI PHỐI NGẪU lại chốt được từ: chồng của một người
    # vai dưới bên ngoại thì là dượng, dù người đó là cậu hay dì. Cờ nghi
    # ngờ vẫn giữ nguyên vì từ máu mủ dẫn ra nó còn đang phân vân.
    ('anh/chị', 'nam'): 'anh',
    ('anh/chị', 'nu'): 'chị',
    ('chú/cô', 'nam'): 'chú',
    ('chú/cô', 'nu'): 'thím',
    ('cậu/dì', 'nam'): 'dượng',
    ('cậu/dì', 'nu'): 'mợ',
}

# Từ máu mủ -> từ mà NGƯỜI KẾT HÔN VÀO HỌ dùng cho cùng người đó.
#
# Luật "gọi theo chồng/vợ" cho con dâu mượn nguyên cách xưng hô của chồng,
# nhưng `nội`/`ngoại` là lời khẳng định huyết thống -- đó chính là lý do
# `('ông nội', 'nu') -> 'bà'` ở trên tồn tại. Hai chỗ phải cùng một luật,
# nên con dâu gọi ông của chồng là `ông`, không phải `ông nội`. Đây cũng là
# dạng xưng hô trực tiếp (nói "ông ơi", không ai nói "ông nội ơi").
#
# CHỈ những từ mang `nội`/`ngoại`. `cụ ông`/`kỵ bà` chỉ đánh dấu giới tính
# chứ không khẳng định dòng máu, nên đi qua nguyên vẹn.
MARRIED_IN_SUBSTITUTES = {
    'ông nội': 'ông',
    'bà nội': 'bà',
    'ông ngoại': 'ông',
    'bà ngoại': 'bà',
}

# Người phối ngẫu của chính mình.
SPOUSE_TERMS = {'nam': 'chồng', 'nu': 'vợ'}
