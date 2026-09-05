"""Tính chất BẮT BUỘC của bảng xưng hô: hai chiều phải khớp nhau.

Đây là bài test mà lẽ ra phải có từ đầu. `test_kinship.py` kiểm tra từng ô
của bảng một cách riêng lẻ, nên một cái thang lệch một nấc (ông ↔ chắt thay
vì ông ↔ cháu) vẫn xanh: mỗi ô đều "đúng theo bảng", chỉ có bảng tự mâu
thuẫn với chính nó. Bài này quét MỌI cặp trong một dòng họ dựng sẵn và bắt
buộc: nếu A gọi B là X thì B phải gọi A đúng bằng từ đối ứng của X.

Dòng họ dưới đây được dựng để chạm tới TỪNG giá trị trong `TERMS` cộng hai
từ chung chung -- `test_every_word_in_the_table_is_reached` chốt điều đó, để
một ô mới thêm vào bảng mà không có ai trong cây chạm tới sẽ bị phát hiện.

BA TẦNG, VÌ MỘT MÌNH PHÉP ĐỐI ỨNG KHÔNG ĐỦ
------------------------------------------
1. `RECIPROCAL` chỉ ràng buộc ĐỘ SÂU của thang: `bác`, `chú`, `cô`, `cậu`,
   `dì`, `ông`, `bà` đều đối ứng bằng `cháu`, nên đổi `bác` bên ngoại thành
   `cậu` (đúng lỗi H2) vẫn lọt qua phép quét. Vì thế có thêm `BY_HAND`:
   một bảng viết tay chốt CHỌN TỪ NÀO ở gap 0 và gap 1, tức chốt cả bên
   nội/ngoại lẫn thứ bậc, chứ không chỉ số đời.
2. Phép quét máu mủ bỏ qua mọi cặp có từ `None` và `RECIPROCAL.get` bỏ qua
   mọi từ hedge, nên hedge hoàn toàn không được kiểm. `HEDGE_ROWS` +
   `HEDGE_RECIPROCAL` quét riêng phần đó.
3. Và một tính chất không cần bảng nào: một hedge không được chứa cái từ mà
   chiều ngược lại đã khẳng định chắc chắn là sai.

`RECIPROCAL`, `BY_HAND`, `HEDGE_RECIPROCAL` đều VIẾT TAY và không dẫn xuất
từ `TERMS`. Đó là toàn bộ giá trị của chúng: một bảng tự kiểm tra chính nó
thì không kiểm gì cả.
"""

from django.test import SimpleTestCase

from giapha.services.kinship import resolve_kinship
from giapha.services.kinship_lookup import resolve_term
from giapha.services.kinship_affinal_terms import AFFINAL_TERMS
from giapha.services.kinship_terms import (
    AMBIGUOUS_TERMS,
    GENERIC_ANCESTOR,
    GENERIC_DESCENDANT,
    TERMS,
)

TO_TIEN = 98
KY_ONG, KY_BA, CU_ONG, CU_BA, ONG_NOI, BA_NOI = 100, 101, 102, 103, 104, 105
BO, BAC, CO_EM, CHU = 106, 107, 108, 109
ONG_NGOAI, BA_NGOAI, ME, CAU, DI, BAC_NGOAI = 120, 121, 122, 123, 124, 125
TOI, EM_RUOT = 130, 131
CON, CHAU, CHAT, CHUT, CHIT, DOI_SAU = 132, 133, 134, 135, 136, 137
ANH_HO, CHI_HO = 140, 146
HO_2, HO_3, HO_4, HO_5, HO_6 = 141, 142, 143, 144, 145


def person(pid, ho_ten, gioi_tinh='nam', father=None, mother=None, birth_order=None):
    return {
        'id': pid, 'ho_ten': ho_ten, 'gioi_tinh': gioi_tinh,
        'father_id': father, 'mother_id': mother, 'birth_order': birth_order,
    }


ROWS = [
    # Trực hệ bên nội, 5 đời trên TOI.
    person(TO_TIEN, 'Tổ tiên'),
    person(KY_ONG, 'Kỵ ông', father=TO_TIEN, birth_order=1),
    person(KY_BA, 'Kỵ bà', 'nu'),
    person(CU_ONG, 'Cụ ông', father=KY_ONG, mother=KY_BA, birth_order=1),
    person(CU_BA, 'Cụ bà', 'nu'),
    person(ONG_NOI, 'Ông nội', father=CU_ONG, mother=CU_BA, birth_order=1),
    person(BA_NOI, 'Bà nội', 'nu'),
    person(BAC, 'Bác trai', father=ONG_NOI, mother=BA_NOI, birth_order=1),
    person(BO, 'Bố', father=ONG_NOI, mother=BA_NOI, birth_order=2),
    person(CO_EM, 'Cô', 'nu', father=ONG_NOI, mother=BA_NOI, birth_order=3),
    person(CHU, 'Chú', father=ONG_NOI, mother=BA_NOI, birth_order=4),
    # Trực hệ bên ngoại.
    person(ONG_NGOAI, 'Ông ngoại'),
    person(BA_NGOAI, 'Bà ngoại', 'nu'),
    person(BAC_NGOAI, 'Bác bên ngoại', father=ONG_NGOAI, mother=BA_NGOAI, birth_order=1),
    person(ME, 'Mẹ', 'nu', father=ONG_NGOAI, mother=BA_NGOAI, birth_order=2),
    person(CAU, 'Cậu', father=ONG_NGOAI, mother=BA_NGOAI, birth_order=3),
    person(DI, 'Dì', 'nu', father=ONG_NGOAI, mother=BA_NGOAI, birth_order=4),
    # TOI và hậu duệ trực hệ, 6 đời xuống.
    person(TOI, 'Tôi', father=BO, mother=ME, birth_order=1),
    person(EM_RUOT, 'Em ruột', father=BO, mother=ME, birth_order=2),
    person(CON, 'Con', father=TOI, birth_order=1),
    person(CHAU, 'Cháu', father=CON, birth_order=1),
    person(CHAT, 'Chắt', father=CHAU, birth_order=1),
    person(CHUT, 'Chút', father=CHAT, birth_order=1),
    person(CHIT, 'Chít', father=CHUT, birth_order=1),
    person(DOI_SAU, 'Đời sau nữa', father=CHIT, birth_order=1),
    # Nhánh bàng hệ của bác, 6 đời xuống -- nguồn của mọi cặp chênh đời.
    person(ANH_HO, 'Anh họ', father=BAC, birth_order=1),
    person(CHI_HO, 'Chị họ', 'nu', father=BAC, birth_order=2),
    person(HO_2, 'Họ đời 2', father=ANH_HO, birth_order=1),
    person(HO_3, 'Họ đời 3', father=HO_2, birth_order=1),
    person(HO_4, 'Họ đời 4', father=HO_3, birth_order=1),
    person(HO_5, 'Họ đời 5', father=HO_4, birth_order=1),
    person(HO_6, 'Họ đời 6', father=HO_5, birth_order=1),
]

IDS = [row['id'] for row in ROWS]

# Từ đối ứng đã được ghi rõ: nếu A gọi B là khoá thì B gọi A là một trong các
# giá trị. Chỉ liệt kê chiều ĐI LÊN (và anh/chị), vì chiều đi xuống gộp nhiều
# quan hệ vào cùng một từ (`cháu` đối ứng với cả ông, bác lẫn cậu) nên không
# xác định được một chiều duy nhất. Mỗi cặp vẫn được kiểm ít nhất một lần,
# ở chiều mà từ đi lên là khoá.
#
# `tổ tiên` nhận hai giá trị: quá nấc thang được viết ra, chiều lên gộp về một
# từ chung trong khi chiều xuống vẫn còn `chít` ở nấc 5.
RECIPROCAL = {
    'bố': ('con',),
    'mẹ': ('con',),
    'ông nội': ('cháu',),
    'bà nội': ('cháu',),
    'ông ngoại': ('cháu',),
    'bà ngoại': ('cháu',),
    'cụ ông': ('chắt',),
    'cụ bà': ('chắt',),
    'kỵ ông': ('chút',),
    'kỵ bà': ('chút',),
    'bác': ('cháu',),
    'chú': ('cháu',),
    'cô': ('cháu',),
    'cậu': ('cháu',),
    'dì': ('cháu',),
    'ông': ('cháu',),
    'bà': ('cháu',),
    'cụ': ('chắt',),
    'kỵ': ('chút',),
    'anh': ('em',),
    'chị': ('em',),
    GENERIC_ANCESTOR: ('chít', GENERIC_DESCENDANT),
}


# Chốt tay TỪ NÀO ở gap 0 và gap 1 -- nơi `RECIPROCAL` mù. Viết theo quan hệ
# thật, không tra bảng: nếu ai đó đổi `bác` bên ngoại về `cậu`, dòng
# `(TOI, BAC_NGOAI)` phải đỏ.
BY_HAND = {
    # Bên nội: anh của bố là bác, em trai là chú, em gái là cô.
    (TOI, BAC): ('bác', 'cháu'),
    (TOI, CO_EM): ('cô', 'cháu'),
    (TOI, CHU): ('chú', 'cháu'),
    # Bên ngoại: anh của mẹ CŨNG là bác (chuẩn miền Bắc), em trai mới là cậu.
    (TOI, BAC_NGOAI): ('bác', 'cháu'),
    (TOI, CAU): ('cậu', 'cháu'),
    (TOI, DI): ('dì', 'cháu'),
    # Trực hệ: nội và ngoại không được lẫn.
    (TOI, ONG_NOI): ('ông nội', 'cháu'),
    (TOI, BA_NOI): ('bà nội', 'cháu'),
    (TOI, ONG_NGOAI): ('ông ngoại', 'cháu'),
    (TOI, BA_NGOAI): ('bà ngoại', 'cháu'),
    (TOI, CU_ONG): ('cụ ông', 'chắt'),
    (TOI, KY_ONG): ('kỵ ông', 'chút'),
    # Cùng đời: vai vế theo NHÁNH, con của bác là anh dù sinh sau.
    (TOI, ANH_HO): ('anh', 'em'),
    (TOI, CHI_HO): ('chị', 'em'),
    (TOI, EM_RUOT): ('em', 'anh'),
    # Bàng hệ chênh đời: đối ứng từng nấc.
    (CON, BAC): ('ông', 'cháu'),
    (CHAU, BAC): ('cụ', 'chắt'),
    (CHAT, BAC): ('kỵ', 'chút'),
}

# Dòng họ thứ hai: thiếu dữ liệu ở đúng những chỗ sinh ra hedge. Cây trên
# gán `birth_order` gần như khắp nơi nên hedge hầu như không xuất hiện.
MO_ONG, MO_BO, MO_NAM, MO_NU, MO_CA_HAI = 200, 201, 202, 203, 204
MO_TREN, MO_DUOI, MO_TOI = 205, 206, 210
MO_EM_NAM, MO_EM_NU, MO_EM_KHAC, MO_ANH_KHAC, MO_EM_DUOI = 211, 212, 213, 214, 215
MO_ONG_NGOAI, MO_ME, MO_NGOAI_NAM, MO_NGOAI_NU = 220, 221, 222, 223
MO_NGOAI_KHAC, MO_NGOAI_DUOI = 224, 225

HEDGE_ROWS = [
    person(MO_ONG, 'Ông nội'),
    person(MO_BO, 'Bố', father=MO_ONG, birth_order=2),
    # Chưa xếp thứ tự -> chưa biết bác hay chú/cô.
    person(MO_NAM, 'Bác hay chú?', father=MO_ONG),
    person(MO_NU, 'Bác hay cô?', 'nu', father=MO_ONG),
    person(MO_CA_HAI, 'Chưa rõ cả hai', 'khac', father=MO_ONG),
    # Biết thứ bậc, chưa biết giới tính.
    person(MO_TREN, 'Vai trên chưa rõ giới', 'khac', father=MO_ONG, birth_order=1),
    person(MO_DUOI, 'Vai dưới chưa rõ giới', 'khac', father=MO_ONG, birth_order=3),
    # Bên ngoại, cùng các hình đó.
    person(MO_ONG_NGOAI, 'Ông ngoại'),
    person(MO_ME, 'Mẹ', 'nu', father=MO_ONG_NGOAI, birth_order=2),
    person(MO_NGOAI_NAM, 'Bác hay cậu?', father=MO_ONG_NGOAI),
    person(MO_NGOAI_NU, 'Bác hay dì?', 'nu', father=MO_ONG_NGOAI),
    person(MO_NGOAI_KHAC, 'Chưa rõ cả hai (ngoại)', 'khac', father=MO_ONG_NGOAI),
    person(MO_NGOAI_DUOI, 'Cậu hay dì?', 'khac', father=MO_ONG_NGOAI, birth_order=3),
    # Đời của người tra cứu.
    person(MO_TOI, 'Tôi', father=MO_BO, mother=MO_ME, birth_order=2),
    person(MO_EM_NAM, 'Anh em chưa xếp thứ tự (nam)', father=MO_BO),
    person(MO_EM_NU, 'Anh em chưa xếp thứ tự (nữ)', 'nu', father=MO_BO),
    person(MO_EM_KHAC, 'Chưa rõ gì cả', 'khac', father=MO_BO),
    person(MO_ANH_KHAC, 'Nhánh trên, chưa rõ giới', 'khac', father=MO_BO, birth_order=1),
    person(MO_EM_DUOI, 'Nhánh dưới, chưa rõ giới', 'khac', father=MO_BO, birth_order=3),
]

HEDGE_IDS = [row['id'] for row in HEDGE_ROWS]

# Hedge -> những từ chiều ngược lại được phép trả về. Viết tay như trên.
# Nhiều giá trị ở nhóm cùng đời vì bên kia có thể cũng đang thiếu dữ liệu
# của chính nó; nhóm chênh đời và `anh/chị` thì chỉ có MỘT đáp án đúng.
SIBLING_HEDGES = ('anh/em', 'chị/em', 'anh/chị/em')
HEDGE_RECIPROCAL = {
    'anh/em': SIBLING_HEDGES,
    'chị/em': SIBLING_HEDGES,
    'anh/chị/em': SIBLING_HEDGES,
    # Đã biết là nhánh trên -> chiều kia chắc chắn `em`, không hedge nữa.
    'anh/chị': ('em',),
    'bác/chú': ('cháu',),
    'bác/cô': ('cháu',),
    'bác/chú/cô': ('cháu',),
    'chú/cô': ('cháu',),
    'bác/cậu': ('cháu',),
    'bác/dì': ('cháu',),
    'bác/cậu/dì': ('cháu',),
    'cậu/dì': ('cháu',),
}

# Một từ chắc chắn ở chiều này LOẠI BỎ những từ nào ở chiều kia. Không tra
# bảng nào: "B gọi A là em" nghĩa là A là nhánh trên, nên A không thể còn
# đang phân vân giữa `em` với thứ khác.
RULED_OUT_BY = {
    'em': ('em',),
    'anh': ('anh', 'chị'),
    'chị': ('anh', 'chị'),
}


def hedge_sweep():
    """`(a_id, b_id, a_calls_b, b_calls_a)` trên dòng họ thiếu dữ liệu."""
    for a_id in HEDGE_IDS:
        for b_id in HEDGE_IDS:
            if a_id == b_id:
                continue
            answer = resolve_kinship(HEDGE_ROWS, a_id, b_id)
            a_calls_b = answer['a_calls_b']
            b_calls_a = answer['b_calls_a']
            if a_calls_b['term'] is None or b_calls_a['term'] is None:
                continue
            yield a_id, b_id, a_calls_b, b_calls_a


def sweep():
    """`(a_id, b_id, a_calls_b, b_calls_a)` cho mọi cặp có quan hệ máu mủ."""
    for a_id in IDS:
        for b_id in IDS:
            if a_id == b_id:
                continue
            result = resolve_kinship(ROWS, a_id, b_id)
            a_calls_b = result['a_calls_b']['term']
            b_calls_a = result['b_calls_a']['term']
            if a_calls_b is None or b_calls_a is None:
                continue
            yield a_id, b_id, a_calls_b, b_calls_a


class ReciprocityTests(SimpleTestCase):
    def test_every_pair_addresses_each_other_consistently(self):
        """Bài test duy nhất bắt được cả một cái thang lệch nấc."""
        for a_id, b_id, a_calls_b, b_calls_a in sweep():
            expected = RECIPROCAL.get(a_calls_b)
            if expected is None:
                continue
            self.assertIn(
                b_calls_a, expected,
                '{a} gọi {b} là "{t1}" nhưng {b} gọi lại là "{t2}"; '
                'từ đối ứng phải là {exp}'.format(
                    a=a_id, b=b_id, t1=a_calls_b, t2=b_calls_a, exp=expected,
                ),
            )

    def test_every_word_in_the_table_is_reached(self):
        """Cây trên phải chạm tới từng ô của bảng, nếu không phép kiểm đối
        ứng ở trên chỉ đang quét một phần bảng mà không ai biết.
        """
        seen = set(a_calls_b for _a, _b, a_calls_b, _r in sweep())
        expected = set(TERMS.values()) | {GENERIC_ANCESTOR, GENERIC_DESCENDANT}
        self.assertEqual(set(), expected - seen)

    def test_side_and_seniority_are_pinned_by_hand_not_only_depth(self):
        """Điểm mù của phép đối ứng: `cháu` đối ứng với cả bác, chú, cậu, dì,
        ông lẫn bà, nên một từ sai bên (nội/ngoại) hay sai thứ bậc vẫn xanh.
        Bảng này chốt đúng phần đó.
        """
        for (a_id, b_id), expected in sorted(BY_HAND.items()):
            answer = resolve_kinship(ROWS, a_id, b_id)
            actual = (answer['a_calls_b']['term'], answer['b_calls_a']['term'])
            self.assertEqual(
                expected, actual,
                'cặp ({a}, {b}) phải là {exp}'.format(a=a_id, b=b_id, exp=expected),
            )
            self.assertTrue(answer['a_calls_b']['confident'])
            self.assertTrue(answer['b_calls_a']['confident'])

    def test_every_hedge_the_sweep_produces_reciprocates_too(self):
        """Hedge cũng phải đối ứng. Phép quét máu mủ ở trên bỏ qua chúng
        hoàn toàn, nên lỗi kiểu H1 sẽ không bị bắt ở đó.
        """
        for a_id, b_id, a_calls_b, b_calls_a in hedge_sweep():
            expected = HEDGE_RECIPROCAL.get(a_calls_b['term'])
            if expected is None:
                continue
            self.assertIn(
                b_calls_a['term'], expected,
                '{a} gọi {b} là "{t1}" nhưng {b} gọi lại là "{t2}"'.format(
                    a=a_id, b=b_id, t1=a_calls_b['term'], t2=b_calls_a['term'],
                ),
            )

    def test_a_hedge_never_offers_a_word_the_other_direction_rules_out(self):
        """Hai ô cạnh nhau trong cùng một câu trả lời không được mâu thuẫn:
        nếu B chắc chắn gọi A là `em` thì A không thể còn phân vân có nên
        gọi B là `em` hay không.
        """
        for a_id, b_id, a_calls_b, b_calls_a in hedge_sweep():
            if not b_calls_a['confident']:
                continue
            forbidden = RULED_OUT_BY.get(b_calls_a['term'], ())
            offered = a_calls_b['term'].split('/')
            for word in forbidden:
                self.assertNotIn(
                    word, offered,
                    '{b} chắc chắn gọi {a} là "{t2}", nên "{t1}" của {a} '
                    'không được còn chứa "{w}"'.format(
                        a=a_id, b=b_id, t1=a_calls_b['term'],
                        t2=b_calls_a['term'], w=word,
                    ),
                )

    def test_the_hedge_clan_really_does_produce_hedges(self):
        """Cây thiếu dữ liệu phải thật sự sinh ra hedge, nếu không hai bài
        trên chỉ đang quét một cây không có gì để quét.
        """
        seen = set(
            a_calls_b['term'] for _a, _b, a_calls_b, _r in hedge_sweep()
            if not a_calls_b['confident']
        )
        self.assertEqual(set(), set(HEDGE_RECIPROCAL) - seen)

    def test_collateral_and_direct_ladders_agree_below_the_ancestor(self):
        """Nấc thang bàng hệ đi xuống lệch đúng MỘT đời so với trực hệ: con
        mình là `con`, cháu của anh mình đã là `cháu`.
        """
        self.assertEqual('con', resolve_kinship(ROWS, TOI, CON)['a_calls_b']['term'])
        self.assertEqual('cháu', resolve_kinship(ROWS, BAC, CON)['a_calls_b']['term'])
        self.assertEqual('cháu', resolve_kinship(ROWS, TOI, CHAU)['a_calls_b']['term'])
        self.assertEqual('chắt', resolve_kinship(ROWS, BAC, CHAU)['a_calls_b']['term'])


class TableIntegrityTests(SimpleTestCase):
    def test_every_affinal_row_keys_off_a_word_the_table_can_produce(self):
        """`AFFINAL_TERMS` tra theo từ máu mủ. Một từ không còn được sinh ra
        (đổi bảng mà quên sửa) thành hàng chết -- lỗi im lặng đúng kiểu đã
        làm hedge `gap == 0` không bao giờ với tới được.
        """
        producible = set(TERMS.values()) | {GENERIC_ANCESTOR, GENERIC_DESCENDANT}
        producible |= set(hedge for hedge, _reason in AMBIGUOUS_TERMS.values())
        for blood_term, _gender in AFFINAL_TERMS:
            self.assertIn(blood_term, producible)

    def test_every_hedge_row_is_reachable(self):
        """Hedge `gap == 0` được đánh khoá `side=None`, nhưng ở gap 0 cả hai
        người đều cách tổ tiên chung ít nhất một đời nên `side` luôn có giá
        trị. Mọi hàng trong `AMBIGUOUS_TERMS` phải thật sự tra ra được.
        """
        unreachable = []
        for kind, gap, side, gender, elder in AMBIGUOUS_TERMS:
            for one_side in ((side,) if side else ('noi', 'ngoai')):
                answer = resolve_term(kind, gap, one_side, gender, elder)
                if answer['confident'] or answer['term'] is None:
                    unreachable.append((kind, gap, one_side, gender, elder))
        self.assertEqual([], unreachable)
