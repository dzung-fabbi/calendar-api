"""Unit tests for the xưng-hô calculator. No DB.

Everything under test takes the plain dict rows `clan_kinship_rows` returns,
so this runs on `SimpleTestCase` -- same idiom as `test_person_rules.py` and
`test_gio_follow_service.py`.

One clan is shared by every case (`ROWS` below) because the mapping table is
what is being covered, not the fixture wiring: a single tree that contains a
bác, a chú, a cô, a cậu, a dì, five generations up, six down, in-laws and a
pair of relatives with no `birth_order` recorded exercises the whole table.
"""

from django.test import SimpleTestCase

from giapha.services.kinship import resolve_kinship
from giapha.services.kinship_graph import ancestor_index, lowest_common_ancestor
from giapha.services.kinship_terms import (
    REASON_AFFINAL_NO_TERM,
    REASON_AMBIGUOUS_MARRIAGE,
    REASON_MISSING_BIRTH_ORDER,
    REASON_MISSING_GENDER,
    REASON_NO_BLOOD,
    REASON_OUT_OF_TABLE,
    REASON_SAME_PERSON,
)

# --- ids, named so the assertions read like the relationship they check ---
TO_TIEN, KY, CU, ONG_NOI, BA_NOI = 29, 30, 31, 1, 2
BAC_GAI, BAC_TRAI, BO, CHU, CO = 7, 3, 4, 5, 6
BAC_MO_BIRTH_ORDER, CO_MO_BIRTH_ORDER, KHAC_GIOI = 8, 9, 13
ONG_NGOAI, BA_NGOAI, ME, CAU, DI = 20, 21, 22, 23, 24
BAC_NGOAI, CAU_MO_BIRTH_ORDER, KHAC_GIOI_NGOAI = 25, 26, 27
TOI, ANH_HO, EM_RUOT = 10, 11, 12
EM_MO_BIRTH_ORDER, CHI_MO_BIRTH_ORDER = 15, 16
CON, CHAU, CHAT, CHUT, CHIT, DOI_SAU = 40, 41, 42, 43, 44, 45
CHAU_HO = 50
THIM, MO, CHONG_CO, DUONG, VO_TOI = 60, 61, 62, 63, 70
VO_CU, ME_KE, VO_BAC_MO_BIRTH_ORDER, CHONG_KHAC_GIOI = 71, 72, 73, 74


def person(pid, ho_ten, gioi_tinh='nam', father=None, mother=None, birth_order=None):
    return {
        'id': pid, 'ho_ten': ho_ten, 'gioi_tinh': gioi_tinh,
        'father_id': father, 'mother_id': mother, 'birth_order': birth_order,
    }


ROWS = [
    person(TO_TIEN, 'Tổ tiên đời 5'),
    person(KY, 'Kỵ ông', father=TO_TIEN),
    person(CU, 'Cụ ông', father=KY),
    person(ONG_NOI, 'Ông nội', father=CU),
    person(BA_NOI, 'Bà nội', 'nu'),
    # Con của ông bà nội, xếp theo birth_order.
    person(BAC_GAI, 'Bác gái', 'nu', father=ONG_NOI, mother=BA_NOI, birth_order=1),
    person(BAC_TRAI, 'Bác trai', father=ONG_NOI, mother=BA_NOI, birth_order=2),
    person(BO, 'Bố', father=ONG_NOI, mother=BA_NOI, birth_order=3),
    person(CHU, 'Chú', father=ONG_NOI, mother=BA_NOI, birth_order=4),
    person(CO, 'Cô', 'nu', father=ONG_NOI, mother=BA_NOI, birth_order=5),
    # Hai người thiếu birth_order -- không được đoán bác hay chú.
    person(BAC_MO_BIRTH_ORDER, 'Chưa rõ thứ bậc (nam)', father=ONG_NOI, mother=BA_NOI),
    person(CO_MO_BIRTH_ORDER, 'Chưa rõ thứ bậc (nữ)', 'nu', father=ONG_NOI, mother=BA_NOI),
    person(KHAC_GIOI, 'Chưa rõ giới tính', 'khac', father=ONG_NOI, birth_order=1),
    # Bên ngoại.
    person(ONG_NGOAI, 'Ông ngoại'),
    person(BA_NGOAI, 'Bà ngoại', 'nu'),
    person(ME, 'Mẹ', 'nu', father=ONG_NGOAI, mother=BA_NGOAI, birth_order=2),
    person(CAU, 'Cậu', father=ONG_NGOAI, mother=BA_NGOAI, birth_order=3),
    person(DI, 'Dì', 'nu', father=ONG_NGOAI, mother=BA_NGOAI, birth_order=4),
    # Anh của mẹ là bác, không phải cậu (chuẩn miền Bắc chặt).
    person(BAC_NGOAI, 'Bác bên ngoại', father=ONG_NGOAI, mother=BA_NGOAI, birth_order=1),
    person(CAU_MO_BIRTH_ORDER, 'Bên ngoại chưa rõ thứ bậc',
           father=ONG_NGOAI, mother=BA_NGOAI),
    person(KHAC_GIOI_NGOAI, 'Bên ngoại chưa rõ giới tính', 'khac',
           father=ONG_NGOAI, mother=BA_NGOAI, birth_order=5),
    # Đời của người tra cứu.
    person(TOI, 'Tôi', father=BO, mother=ME, birth_order=1),
    person(ANH_HO, 'Anh họ', father=BAC_TRAI, birth_order=1),
    person(EM_RUOT, 'Em ruột', father=BO, mother=ME, birth_order=2),
    # Anh chị em chưa xếp thứ tự -- vẫn phải ra anh/em kèm cờ nghi ngờ.
    person(EM_MO_BIRTH_ORDER, 'Anh em chưa rõ thứ bậc (nam)', father=BO, mother=ME),
    person(CHI_MO_BIRTH_ORDER, 'Anh em chưa rõ thứ bậc (nữ)', 'nu', father=BO, mother=ME),
    person(CHAU_HO, 'Cháu họ', father=ANH_HO, birth_order=1),
    # Hậu duệ trực hệ.
    person(CON, 'Con', father=TOI, birth_order=1),
    person(CHAU, 'Cháu', father=CON, birth_order=1),
    person(CHAT, 'Chắt', father=CHAU, birth_order=1),
    person(CHUT, 'Chút', father=CHAT, birth_order=1),
    person(CHIT, 'Chít', father=CHUT, birth_order=1),
    person(DOI_SAU, 'Đời sau nữa', father=CHIT, birth_order=1),
    # Người kết hôn vào họ -- không cùng huyết thống với TOI.
    person(THIM, 'Thím', 'nu'),
    person(MO, 'Mợ', 'nu'),
    person(CHONG_CO, 'Chồng của cô'),
    person(DUONG, 'Dượng'),
    person(VO_TOI, 'Vợ tôi', 'nu'),
    person(VO_CU, 'Vợ của cụ', 'nu'),
    person(ME_KE, 'Mẹ kế', 'nu'),
    person(VO_BAC_MO_BIRTH_ORDER, 'Vợ của người chưa rõ thứ bậc', 'nu'),
    person(CHONG_KHAC_GIOI, 'Chồng của người chưa rõ giới tính'),
]

def marriage(husband_id, wife_id, status='dang_ket_hon', order=1):
    """One row in the shape `selectors.marriage.clan_spouse_pairs` returns."""
    return (husband_id, wife_id, status, order)


SPOUSES = [
    marriage(CHU, THIM), marriage(CAU, MO), marriage(CHONG_CO, CO),
    marriage(DUONG, DI), marriage(TOI, VO_TOI), marriage(BO, ME),
    marriage(ONG_NOI, BA_NOI), marriage(CU, VO_CU),
    marriage(BO, ME_KE, order=2),
    marriage(BAC_MO_BIRTH_ORDER, VO_BAC_MO_BIRTH_ORDER),
    marriage(CHONG_KHAC_GIOI, KHAC_GIOI_NGOAI),
]


def term(a_id, b_id, spouses=None):
    return resolve_kinship(ROWS, a_id, b_id, spouses=spouses)['a_calls_b']


def both(a_id, b_id, spouses=None):
    result = resolve_kinship(ROWS, a_id, b_id, spouses=spouses)
    return result['a_calls_b']['term'], result['b_calls_a']['term']


class PaternalTests(SimpleTestCase):
    """Anh của bố là bác, em trai là chú, em gái là cô -- chuẩn miền Bắc."""

    def test_elder_brother_of_father_is_bac(self):
        self.assertEqual('bác', term(TOI, BAC_TRAI)['term'])

    def test_elder_sister_of_father_is_also_bac(self):
        self.assertEqual('bác', term(TOI, BAC_GAI)['term'])

    def test_younger_brother_of_father_is_chu(self):
        self.assertEqual('chú', term(TOI, CHU)['term'])

    def test_younger_sister_of_father_is_co(self):
        self.assertEqual('cô', term(TOI, CO)['term'])

    def test_uncle_calls_back_chau(self):
        self.assertEqual(('chú', 'cháu'), both(TOI, CHU))

    def test_paternal_side_is_reported_as_noi(self):
        path = resolve_kinship(ROWS, TOI, CHU)['path']
        self.assertEqual({'a_up': 2, 'b_up': 1, 'side': 'noi'}, path)


class MaternalTests(SimpleTestCase):
    """Bên ngoại CÓ phân thứ bậc: anh/chị của mẹ là bác, em trai là cậu,
    em gái là dì. Đây là chuẩn miền Bắc mà module tự nhận là mã hoá.
    """

    def test_younger_brother_of_mother_is_cau(self):
        self.assertEqual('cậu', term(TOI, CAU)['term'])

    def test_younger_sister_of_mother_is_di(self):
        self.assertEqual('dì', term(TOI, DI)['term'])

    def test_elder_brother_of_mother_is_bac_not_cau(self):
        answer = term(TOI, BAC_NGOAI)
        self.assertEqual('bác', answer['term'])
        self.assertTrue(answer['confident'])

    def test_maternal_uncle_without_birth_order_hedges_like_the_paternal_side(self):
        """Không còn chỗ nào trả `confident: true` cho một từ phụ thuộc
        thứ bậc mà thiếu `birth_order`.
        """
        answer = term(TOI, CAU_MO_BIRTH_ORDER)
        self.assertEqual('bác/cậu', answer['term'])
        self.assertFalse(answer['confident'])
        self.assertEqual(REASON_MISSING_BIRTH_ORDER, answer['reason'])

    def test_maternal_side_is_reported_as_ngoai(self):
        self.assertEqual('ngoai', resolve_kinship(ROWS, TOI, CAU)['path']['side'])


class SiblingAndCousinTests(SimpleTestCase):
    def test_younger_sibling_is_em_and_calls_back_anh(self):
        self.assertEqual(('em', 'anh'), both(TOI, EM_RUOT))

    def test_child_of_elder_uncle_is_anh_regardless_of_age(self):
        """Vai vế theo nhánh, không theo tuổi: con của bác luôn là anh."""
        self.assertEqual(('anh', 'em'), both(TOI, ANH_HO))

    def test_sibling_common_ancestor_is_the_parent(self):
        self.assertEqual(BO, resolve_kinship(ROWS, TOI, EM_RUOT)['common_ancestor']['id'])


class DirectLineTests(SimpleTestCase):
    def test_father_and_mother(self):
        self.assertEqual('bố', term(TOI, BO)['term'])
        self.assertEqual('mẹ', term(TOI, ME)['term'])

    def test_grandparents_distinguish_noi_from_ngoai(self):
        self.assertEqual('ông nội', term(TOI, ONG_NOI)['term'])
        self.assertEqual('bà nội', term(TOI, BA_NOI)['term'])
        self.assertEqual('ông ngoại', term(TOI, ONG_NGOAI)['term'])
        self.assertEqual('bà ngoại', term(TOI, BA_NGOAI)['term'])

    def test_three_and_four_generations_up_are_cu_and_ky(self):
        self.assertEqual('cụ ông', term(TOI, CU)['term'])
        self.assertEqual('kỵ ông', term(TOI, KY)['term'])

    def test_five_generations_up_falls_back_to_generic(self):
        answer = term(TOI, TO_TIEN)
        self.assertEqual('tổ tiên', answer['term'])
        self.assertTrue(answer['confident'])

    def test_descendants_ladder(self):
        self.assertEqual('con', term(TOI, CON)['term'])
        self.assertEqual('cháu', term(TOI, CHAU)['term'])
        self.assertEqual('chắt', term(TOI, CHAT)['term'])
        self.assertEqual('chút', term(TOI, CHUT)['term'])
        self.assertEqual('chít', term(TOI, CHIT)['term'])

    def test_six_generations_down_falls_back_to_generic(self):
        self.assertEqual('hậu duệ', term(TOI, DOI_SAU)['term'])

    def test_grandchild_calls_back_ong_noi(self):
        self.assertEqual(('ông nội', 'cháu'), both(CHAU, TOI))


class CollateralGapTests(SimpleTestCase):
    def test_nephew_of_a_cousin_is_chau(self):
        self.assertEqual('cháu', term(TOI, CHAU_HO)['term'])

    def test_that_nephew_calls_back_chu_not_bac(self):
        """Bố của TOI là em của ông nội CHAU_HO, nên TOI là chú, không phải bác."""
        self.assertEqual('chú', term(CHAU_HO, TOI)['term'])

    def test_two_collateral_generations_up_is_ong(self):
        self.assertEqual('ông', term(CON, BAC_TRAI)['term'])

    def test_three_collateral_generations_up_is_cu(self):
        self.assertEqual('cụ', term(CHAU, BAC_TRAI)['term'])

    def test_two_collateral_generations_down_is_chau_the_reciprocal_of_ong(self):
        """ông ↔ cháu. Cháu của anh trai mình gọi mình là ông, mình gọi nó là
        `cháu` -- `chắt` ở đây là phong nó lên một đời, đúng kiểu sai vai vế
        mà tính năng này tồn tại để tránh.
        """
        self.assertEqual(('ông', 'cháu'), both(CON, BAC_TRAI))

    def test_three_collateral_generations_down_is_chat_the_reciprocal_of_cu(self):
        self.assertEqual(('cụ', 'chắt'), both(CHAU, BAC_TRAI))

    def test_four_collateral_generations_down_is_chut_the_reciprocal_of_ky(self):
        self.assertEqual(('kỵ', 'chút'), both(CHAT, BAC_TRAI))

    def test_five_collateral_generations_down_is_chit(self):
        self.assertEqual('chít', term(BAC_TRAI, CHUT)['term'])

    def test_six_collateral_generations_down_falls_back_to_generic(self):
        self.assertEqual('hậu duệ', term(BAC_TRAI, CHIT)['term'])


class MissingDataTests(SimpleTestCase):
    """Không đoán bừa. Sai vai vế là điều người Việt để bụng."""

    def test_missing_birth_order_hedges_between_bac_and_chu(self):
        answer = term(TOI, BAC_MO_BIRTH_ORDER)
        self.assertEqual('bác/chú', answer['term'])
        self.assertFalse(answer['confident'])
        self.assertEqual(REASON_MISSING_BIRTH_ORDER, answer['reason'])

    def test_missing_birth_order_hedges_between_bac_and_co(self):
        answer = term(TOI, CO_MO_BIRTH_ORDER)
        self.assertEqual('bác/cô', answer['term'])
        self.assertFalse(answer['confident'])

    def test_known_elder_of_unknown_gender_is_confidently_bac(self):
        """`bác` KHÔNG phụ thuộc giới tính khi đã biết người đó là vai trên:
        bảng lưu cùng một từ cho cả 'nam' lẫn 'nu'. Hedge `bác/chú/cô` ở đây
        là vứt đi một câu trả lời chắc chắn mà chẳng thật thà hơn chút nào.
        """
        answer = term(TOI, KHAC_GIOI)
        self.assertEqual('bác', answer['term'])
        self.assertTrue(answer['confident'])

    def test_missing_gender_and_missing_birth_order_hedges_across_all_three(self):
        """Bảo đảm "không đoán bừa" là về THIẾU `birth_order`; thiếu mỗi
        giới tính mà đã biết vai trên thì không cần hedge.
        """
        rows = [
            person(1, 'Ông nội'),
            person(2, 'Bố', father=1),
            person(3, 'Chưa rõ gì cả', 'khac', father=1),
            person(4, 'Tôi', father=2),
        ]
        answer = resolve_kinship(rows, 4, 3)['a_calls_b']
        self.assertEqual('bác/chú/cô', answer['term'])
        self.assertFalse(answer['confident'])

    def test_known_younger_of_unknown_gender_hedges_only_chu_co(self):
        """`bác` đã bị loại vì biết là vai dưới -- hedge không được nhắc lại."""
        rows = [
            person(1, 'Ông nội'),
            person(2, 'Bố', father=1, birth_order=1),
            person(3, 'Chú hay cô?', 'khac', father=1, birth_order=2),
            person(4, 'Tôi', father=2),
        ]
        answer = resolve_kinship(rows, 4, 3)['a_calls_b']
        self.assertEqual('chú/cô', answer['term'])
        self.assertEqual(REASON_MISSING_GENDER, answer['reason'])

    def test_sibling_without_birth_order_still_gets_a_word(self):
        """Gia phả mới nhập thường chưa có `birth_order`. Câu hỏi cơ bản nhất
        của tính năng ("anh hay em?") vẫn phải trả về `anh/em`, không được
        rơi xuống `term: None` kèm slug máy đọc.
        """
        answer = term(TOI, EM_MO_BIRTH_ORDER)
        self.assertEqual('anh/em', answer['term'])
        self.assertFalse(answer['confident'])
        self.assertEqual(REASON_MISSING_BIRTH_ORDER, answer['reason'])

    def test_female_sibling_without_birth_order_hedges_chi_em(self):
        answer = term(TOI, CHI_MO_BIRTH_ORDER)
        self.assertEqual('chị/em', answer['term'])
        self.assertEqual(REASON_MISSING_BIRTH_ORDER, answer['reason'])

    def test_cousin_without_birth_order_hedges_too(self):
        """Cùng lỗi, một đời sâu hơn: hai anh em họ chưa xếp thứ tự."""
        rows = [
            person(1, 'Ông'),
            person(2, 'Bố', father=1),
            person(3, 'Bác hay chú?', father=1),
            person(4, 'Tôi', father=2, birth_order=1),
            person(5, 'Anh hay em họ?', father=3, birth_order=1),
        ]
        answer = resolve_kinship(rows, 4, 5)['a_calls_b']
        self.assertEqual('anh/em', answer['term'])
        self.assertFalse(answer['confident'])

    def test_a_hedge_never_contradicts_the_confident_term_beside_it(self):
        """`b_calls_a = 'em'` khẳng định nhánh của A là vai dưới, nên `em`
        KHÔNG được có mặt trong hedge của A: hai ô cạnh nhau trong cùng một
        câu trả lời sẽ tự mâu thuẫn.
        """
        rows = [
            person(1, 'Bố'),
            person(2, 'Tôi', father=1, birth_order=2),
            person(3, 'Chưa rõ giới tính', 'khac', father=1, birth_order=1),
        ]
        result = resolve_kinship(rows, 2, 3)
        self.assertEqual('anh/chị', result['a_calls_b']['term'])
        self.assertEqual(REASON_MISSING_GENDER, result['a_calls_b']['reason'])
        self.assertEqual('em', result['b_calls_a']['term'])
        self.assertTrue(result['b_calls_a']['confident'])

    def test_sibling_of_unknown_gender_and_no_birth_order_hedges_all_three(self):
        rows = [
            person(1, 'Bố'),
            person(2, 'Tôi', father=1),
            person(3, 'Chưa rõ giới tính', 'khac', father=1),
        ]
        answer = resolve_kinship(rows, 2, 3)['a_calls_b']
        self.assertEqual('anh/chị/em', answer['term'])
        self.assertEqual(REASON_MISSING_GENDER, answer['reason'])

    def test_maternal_aunt_without_birth_order_hedges_bac_di(self):
        rows = [
            person(1, 'Ông ngoại'),
            person(2, 'Mẹ', 'nu', father=1),
            person(3, 'Bác hay dì?', 'nu', father=1),
            person(4, 'Tôi', mother=2),
        ]
        answer = resolve_kinship(rows, 4, 3)['a_calls_b']
        self.assertEqual('bác/dì', answer['term'])
        self.assertFalse(answer['confident'])
        self.assertEqual(REASON_MISSING_BIRTH_ORDER, answer['reason'])

    def test_equal_birth_order_is_treated_as_unknown(self):
        """Hai anh em cùng birth_order là dữ liệu hỏng -- chọn bừa một bên
        chính là câu trả lời sai mà tự tin cần tránh.
        """
        rows = [
            person(1, 'Ông'),
            person(2, 'Bố', father=1, birth_order=1),
            person(3, 'Bác hay chú?', father=1, birth_order=1),
            person(4, 'Tôi', father=2),
        ]
        answer = resolve_kinship(rows, 4, 3)['a_calls_b']
        self.assertEqual('bác/chú', answer['term'])
        self.assertFalse(answer['confident'])


class MarriageTests(SimpleTestCase):
    def test_wife_of_chu_is_thim(self):
        self.assertEqual('thím', term(TOI, THIM, SPOUSES)['term'])

    def test_wife_of_cau_is_mo(self):
        self.assertEqual('mợ', term(TOI, MO, SPOUSES)['term'])

    def test_husband_of_co_is_chu(self):
        self.assertEqual('chú', term(TOI, CHONG_CO, SPOUSES)['term'])

    def test_husband_of_di_is_duong(self):
        self.assertEqual('dượng', term(TOI, DUONG, SPOUSES)['term'])

    def test_in_law_addresses_back_the_way_their_spouse_does(self):
        self.assertEqual('cháu', resolve_kinship(ROWS, TOI, THIM, SPOUSES)['b_calls_a']['term'])

    def test_own_spouse(self):
        self.assertEqual(('vợ', 'chồng'), both(TOI, VO_TOI, SPOUSES))

    def test_own_wife_wins_over_her_earlier_marriage_to_a_brother(self):
        """`goa` được giữ lại trong `clan_spouse_pairs`, nên tái hôn sau khi
        chồng mất là chuyện thường. Vợ mình không được trả về là `chị` chỉ vì
        người chồng trước có id nhỏ hơn.
        """
        rows = [
            person(1, 'Bố'),
            person(5, 'Anh', father=1, birth_order=1),
            person(9, 'Tôi', father=1, birth_order=2),
            person(20, 'Vợ', 'nu'),
        ]
        spouses = [marriage(5, 20, status='goa'), marriage(9, 20)]
        result = resolve_kinship(rows, 9, 20, spouses=spouses)
        self.assertEqual('vợ', result['a_calls_b']['term'])
        self.assertEqual('chồng', result['b_calls_a']['term'])
        # Và không phụ thuộc thứ tự id: hỏi ngược lại vẫn thế.
        self.assertEqual('chồng', resolve_kinship(rows, 20, 9, spouses)['a_calls_b']['term'])

    def test_wife_of_cu_is_addressed_cu(self):
        self.assertEqual('cụ', term(TOI, VO_CU, SPOUSES)['term'])

    def test_affinal_answer_names_no_common_ancestor(self):
        """`path`/`common_ancestor` mô tả A với NGƯỜI PHỐI NGẪU của B, không
        phải A với B -- vẽ ra thì sai, nên để trống như cặp vợ chồng.
        """
        result = resolve_kinship(ROWS, TOI, THIM, SPOUSES)
        self.assertIsNone(result['common_ancestor'])
        self.assertEqual({'a_up': None, 'b_up': None, 'side': None}, result['path'])

    def test_hedged_affinal_term_says_what_is_missing(self):
        result = resolve_kinship(ROWS, TOI, VO_BAC_MO_BIRTH_ORDER, SPOUSES)
        self.assertEqual('bác gái/thím', result['a_calls_b']['term'])
        self.assertFalse(result['a_calls_b']['confident'])
        self.assertIn('thiếu birth_order', result['explain'])

    def test_gender_hedge_propagates_through_the_marriage(self):
        """Cờ nghi ngờ về giới tính phải đi tiếp thành cờ nghi ngờ, không
        được biến mất thành "không có quan hệ".
        """
        answer = term(TOI, CHONG_KHAC_GIOI, SPOUSES)
        self.assertEqual('dượng', answer['term'])
        self.assertFalse(answer['confident'])
        self.assertEqual(REASON_MISSING_GENDER, answer['reason'])


class SpouseRoutingTests(SimpleTestCase):
    """QUA NGƯỜI PHỐI NGẪU NÀO là một quyết định, không phải một tai nạn.

    Trước đây `clan_spouse_pairs` bỏ mất `status`/`order` nên dịch vụ chỉ còn
    biết sắp theo id tự tăng -- tức là theo thứ tự nhập liệu. Vợ của em trai
    bị bảo gọi anh chồng là `em` chỉ vì người chồng trước (đã mất) có id nhỏ
    hơn. Cả hai bài dưới đây đều dựng đúng hình đó.
    """

    LEVIRATE_ROWS = [
        person(1, 'Bố'),
        person(2, 'Anh', father=1, birth_order=1),
        person(3, 'X', father=1, birth_order=2),
        person(4, 'Em', father=1, birth_order=3),
        person(20, 'Dâu', 'nu'),
    ]

    def test_the_current_husband_outranks_the_late_one(self):
        """Goá chồng rồi tái hôn với em chồng: phải tính theo chồng HIỆN TẠI."""
        spouses = [marriage(2, 20, status='goa'), marriage(4, 20)]
        result = resolve_kinship(self.LEVIRATE_ROWS, 20, 3, spouses=spouses)
        self.assertEqual('anh', result['a_calls_b']['term'])
        self.assertTrue(result['a_calls_b']['confident'])
        self.assertEqual('em', result['b_calls_a']['term'])

    def test_that_answer_does_not_depend_on_which_row_was_entered_first(self):
        """Cùng dữ liệu, đảo thứ tự dòng và đảo cả chiều hỏi."""
        spouses = [marriage(4, 20), marriage(2, 20, status='goa')]
        self.assertEqual(
            'anh',
            resolve_kinship(self.LEVIRATE_ROWS, 20, 3, spouses)['a_calls_b']['term'],
        )
        self.assertEqual(
            'em',
            resolve_kinship(self.LEVIRATE_ROWS, 3, 20, spouses)['a_calls_b']['term'],
        )

    def test_a_second_wife_is_ranked_by_marriage_order_not_by_id(self):
        """Đa thê: `Marriage.order` (1 = vợ cả) quyết định, id thì không.

        Vợ cả ở đây có id LỚN hơn vợ lẽ, nên sắp theo id sẽ ra `em`.
        """
        rows = [
            person(1, 'Ông ngoại'),
            person(2, 'Vợ lẽ', 'nu', father=1, birth_order=3),
            person(3, 'Tôi', father=1, birth_order=2),
            person(4, 'Vợ cả', 'nu', father=1, birth_order=1),
            person(10, 'Chồng của hai bà'),
        ]
        spouses = [marriage(10, 4, order=1), marriage(10, 2, order=2)]
        answer = resolve_kinship(rows, 3, 10, spouses)['a_calls_b']
        self.assertEqual('anh', answer['term'])
        self.assertTrue(answer['confident'])

    def test_two_equally_ranked_live_marriages_hedge_instead_of_guessing(self):
        """Hai cuộc hôn nhân còn hiệu lực, cùng `order`: dữ liệu không nói
        được cuộc nào là hiện tại. Chọn bừa một bên chính là câu trả lời tự
        tin mà sai -- phải hạ cờ `confident` xuống.
        """
        spouses = [marriage(2, 20), marriage(4, 20)]
        result = resolve_kinship(self.LEVIRATE_ROWS, 20, 3, spouses=spouses)
        self.assertFalse(result['a_calls_b']['confident'])
        self.assertEqual(REASON_AMBIGUOUS_MARRIAGE, result['a_calls_b']['reason'])
        self.assertFalse(result['b_calls_a']['confident'])

    def test_one_marriage_alone_is_never_reported_as_ambiguous(self):
        spouses = [marriage(4, 20)]
        answer = resolve_kinship(self.LEVIRATE_ROWS, 20, 3, spouses)['a_calls_b']
        self.assertEqual('anh', answer['term'])
        self.assertTrue(answer['confident'])


class AffinalExplainTests(SimpleTestCase):
    def test_the_explanation_justifies_the_word_it_shows(self):
        """Chiều được soi gương phải có câu giải thích của CHÍNH chiều đó.
        Trước đây câu văn được chép nguyên từ lời gọi ngược lại, nên hiện
        `bố` mà lại giải thích cho `con`.
        """
        result = resolve_kinship(ROWS, VO_TOI, BO, SPOUSES)
        self.assertEqual('bố', result['a_calls_b']['term'])
        self.assertIn('Vợ tôi kết hôn với Tôi', result['explain'])
        self.assertIn('Tôi gọi Bố là bố', result['explain'])
        self.assertIn('nên Vợ tôi gọi Bố là bố', result['explain'])
        self.assertNotIn('Bố gọi Tôi là con', result['explain'])

    def test_the_ordinary_direction_still_explains_itself(self):
        result = resolve_kinship(ROWS, TOI, THIM, SPOUSES)
        self.assertIn('Thím kết hôn với Chú', result['explain'])
        self.assertIn('Tôi gọi Chú là chú', result['explain'])


class MarriedInAddressTests(SimpleTestCase):
    """`ông nội`/`bà ngoại` hàm ý huyết thống -- `kinship_affinal_terms` nói
    thế và đã dùng đúng lý do đó cho vợ sau của ông. Con dâu cũng không phải
    hậu duệ, nên chiều còn lại phải theo cùng một luật.
    """

    def test_a_daughter_in_law_says_ong_not_ong_noi(self):
        self.assertEqual('ông', term(VO_TOI, ONG_NOI, SPOUSES)['term'])

    def test_and_is_still_called_chau_back(self):
        result = resolve_kinship(ROWS, VO_TOI, ONG_NOI, SPOUSES)
        self.assertEqual('cháu', result['b_calls_a']['term'])

    def test_the_words_without_a_blood_claim_pass_through_unchanged(self):
        self.assertEqual('bố', term(VO_TOI, BO, SPOUSES)['term'])
        self.assertEqual('cụ ông', term(VO_TOI, CU, SPOUSES)['term'])


class ReasonSlugTests(SimpleTestCase):
    """`reason` là ô mà client rẽ nhánh, nên phải máy đọc được -- không trộn
    slug ASCII với tiếng Việt có dấu. Chữ cho người đọc nằm ở `explain`.
    """

    def test_every_reason_value_is_an_ascii_slug(self):
        for reason in (
            REASON_MISSING_BIRTH_ORDER, REASON_MISSING_GENDER, REASON_NO_BLOOD,
            REASON_AFFINAL_NO_TERM, REASON_AMBIGUOUS_MARRIAGE,
            REASON_SAME_PERSON, REASON_OUT_OF_TABLE,
        ):
            self.assertRegex(reason, r'^[a-z0-9_]+$')

    def test_the_vietnamese_wording_still_reaches_the_reader(self):
        result = resolve_kinship(ROWS, TOI, BAC_MO_BIRTH_ORDER)
        self.assertEqual(REASON_MISSING_BIRTH_ORDER, result['a_calls_b']['reason'])
        self.assertIn('thiếu birth_order', result['explain'])


class AffinalWithoutAWordTests(SimpleTestCase):
    """Có quan hệ hôn nhân nhưng không có từ thông dụng ≠ không có quan hệ."""

    def test_stepmother_hedges_instead_of_claiming_no_relation(self):
        answer = term(TOI, ME_KE, SPOUSES)
        self.assertIsNone(answer['term'])
        self.assertFalse(answer['confident'])
        self.assertNotEqual(REASON_NO_BLOOD, answer['reason'])
        self.assertEqual(REASON_AFFINAL_NO_TERM, answer['reason'])

    def test_that_answer_names_the_spouse_it_went_through(self):
        self.assertIn('Bố', resolve_kinship(ROWS, TOI, ME_KE, SPOUSES)['explain'])

    def test_a_real_stranger_still_reports_no_blood_confidently(self):
        answer = term(TOI, 99999, SPOUSES)
        self.assertEqual(REASON_NO_BLOOD, answer['reason'])
        self.assertTrue(answer['confident'])


class MarriedInMemberTests(SimpleTestCase):
    """Người mới về làm dâu/rể là đối tượng dùng tính năng này nhiều nhất --
    họ không có huyết thống với ai, nên phải tính qua vợ/chồng của họ.
    """

    def test_wife_addresses_her_husbands_uncle_the_way_he_does(self):
        self.assertEqual(('chú', 'cháu'), both(VO_TOI, CHU, SPOUSES))

    def test_wife_calls_her_husbands_father_bo_and_is_called_con(self):
        self.assertEqual(('bố', 'con'), both(VO_TOI, BO, SPOUSES))

    def test_wife_addresses_her_husbands_elder_cousin_as_anh(self):
        self.assertEqual('anh', term(VO_TOI, ANH_HO, SPOUSES)['term'])

    def test_two_people_who_both_married_in_get_no_derived_term(self):
        """Giới hạn có chủ ý: chỉ đi MỘT cạnh hôn nhân. Vợ tôi với thím phải
        qua hai cạnh (vợ tôi -> tôi -> chú -> thím) nên không suy ra từ nào.
        """
        answer = term(VO_TOI, THIM, SPOUSES)
        self.assertIsNone(answer['term'])
        self.assertEqual(REASON_NO_BLOOD, answer['reason'])

    def test_without_spouse_data_the_same_pair_reads_as_unrelated(self):
        """Vì sao view nạp bảng hôn nhân lười: chỉ khi không có huyết thống
        thì cạnh hôn nhân mới đổi được câu trả lời.
        """
        answer = term(TOI, THIM)
        self.assertIsNone(answer['term'])
        self.assertEqual(REASON_NO_BLOOD, answer['reason'])


class NoRelationTests(SimpleTestCase):
    def test_no_common_ancestor_is_an_answer_not_an_error(self):
        result = resolve_kinship(ROWS, TOI, THIM)
        self.assertIsNone(result['a_calls_b']['term'])
        self.assertEqual(REASON_NO_BLOOD, result['a_calls_b']['reason'])
        self.assertIsNone(result['common_ancestor'])
        self.assertEqual({'a_up': None, 'b_up': None, 'side': None}, result['path'])

    def test_same_person_is_named_as_such(self):
        result = resolve_kinship(ROWS, TOI, TOI)
        self.assertIsNone(result['a_calls_b']['term'])
        self.assertEqual(REASON_SAME_PERSON, result['a_calls_b']['reason'])

    def test_unknown_id_does_not_raise(self):
        self.assertIsNone(term(TOI, 99999)['term'])


class GraphTests(SimpleTestCase):
    def test_lowest_common_ancestor_reports_depths_and_side(self):
        self.assertEqual((ONG_NOI, 2, 1, 'noi'), lowest_common_ancestor(ROWS, TOI, CHU))

    def test_side_is_fixed_by_the_first_step_only(self):
        """Mẹ của bố vẫn là bên nội."""
        self.assertEqual('noi', ancestor_index(ROWS, TOI)[BA_NOI][1])

    def test_cycle_entered_by_hand_terminates(self):
        """Django admin bỏ qua `person_rules.validate_no_cycle`, nên vòng lặp
        cha-con có thể đã nằm sẵn trong bảng. Phải dừng, không được treo.
        """
        rows = [person(1, 'A', father=3), person(2, 'B', father=1), person(3, 'C', father=2)]
        self.assertEqual({1, 2, 3}, set(ancestor_index(rows, 1)))
        self.assertIsNotNone(resolve_kinship(rows, 1, 2))

    def test_truncated_walk_stops_early_instead_of_raising(self):
        """Bộ đếm bảo hiểm fail-open: cắt ngắn thì BỎ SÓT tổ tiên, không nổ.

        Cố ý KHÔNG khẳng định "không thể ra từ sai": nếu tổ tiên chung gần
        nhất bị cắt mất mà còn một tổ tiên chung xa hơn, `best_common_ancestor`
        sẽ lấy người xa đó và trả về một từ sai kèm `confident: true`. Bộ đếm
        không thể chạm tới trong thực tế (xem docstring `kinship_graph`), nên
        đây là giới hạn được ghi nhận chứ không phải bảo đảm an toàn.
        """
        index = ancestor_index(ROWS, TOI, max_iterations=1)
        self.assertEqual(0, index[TOI][0])
        self.assertNotIn(ONG_NOI, index)


class ExplainTests(SimpleTestCase):
    def test_explain_names_both_people_and_the_common_ancestor(self):
        explain = resolve_kinship(ROWS, TOI, CHU)['explain']
        for fragment in ('Tôi', 'Chú', 'Ông nội', 'chú', 'cháu'):
            self.assertIn(fragment, explain)

    def test_explain_says_what_is_missing_when_not_confident(self):
        explain = resolve_kinship(ROWS, TOI, BAC_MO_BIRTH_ORDER)['explain']
        self.assertIn('thiếu birth_order', explain)
