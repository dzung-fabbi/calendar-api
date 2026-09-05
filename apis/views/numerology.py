"""Pythagorean numerology endpoint (`so-hoc`)."""

from statistics import mode

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apis.services.numerology import (
    letter_values,
    reduce_keeping_master,
    reduce_to_single_digit,
    strip_accents,
)
from apis.views.params import InvalidParam, required

BIRTH_DAY_LENGTH = 8

# Karmic debt numbers, matched by their leading digits.
KARMIC_DEBTS = ['13/4', '14/5', '16/7', '19/1']


class SoHocAPIView(APIView):
    def get(self, request):
        birth_day = self._validated_birth_day(request)
        full_name = self._validated_full_name(request)
        phone = self._validated_phone(request)

        numbers = self._birth_numbers(birth_day)
        name_numbers = self._name_numbers(full_name, numbers['so_chu_dao'])
        return Response(data=dict(
            numbers,
            **name_numbers,
            so_thieu='',
            so_dien_thoai=reduce_to_single_digit(phone),
        ))

    @staticmethod
    def _validated_birth_day(request):
        """DDMMYYYY. Only the first four characters are read, but the whole
        value feeds the life-path sum, so all eight must be digits."""
        value = required(request, 'birth_day')
        if len(value) != BIRTH_DAY_LENGTH or not value.isdigit():
            raise InvalidParam('birth_day', 'phải có dạng DDMMYYYY')
        return value

    @staticmethod
    def _validated_full_name(request):
        value = required(request, 'full_name')
        if not strip_accents(value).strip():
            raise InvalidParam('full_name', 'không được rỗng')
        return value

    @staticmethod
    def _validated_phone(request):
        value = required(request, 'phone')
        if not value.isdigit():
            raise InvalidParam('phone', 'chỉ được chứa chữ số')
        return value

    def _birth_numbers(self, birth_day):
        """Numbers derived from the birth date alone (format DDMMYYYY)."""
        sum_birth_day = sum(int(x) for x in str(birth_day) if x.isdigit())
        so_chu_dao = reduce_to_single_digit(sum_birth_day)

        sum_ngay = int(birth_day[0]) + int(birth_day[1])
        so_ngay_sinh = reduce_to_single_digit(sum_ngay)
        sum_thang = int(birth_day[2]) + int(birth_day[3])
        so_thang_sinh = reduce_to_single_digit(sum_thang)
        so_nam_sinh = reduce_to_single_digit(sum_birth_day - sum_thang - sum_ngay)

        so_thai_do = reduce_to_single_digit(so_ngay_sinh + so_thang_sinh)
        so_nam_the_gioi = reduce_to_single_digit(timezone.now().year)
        so_nam_ca_nhan = reduce_to_single_digit(so_nam_the_gioi + so_thai_do)

        tuoi_dinh_cao_1 = 36 - so_chu_dao
        dinh_cao_1 = reduce_to_single_digit(so_ngay_sinh + so_thang_sinh)
        dinh_cao_2 = reduce_to_single_digit(so_ngay_sinh + so_nam_sinh)

        # Challenge numbers. 1 and 2 come from the day/month/year digits; the
        # third is derived from the first two. The original computed the same
        # expression for 3 and 4, so one of them was dead weight.
        thu_thach_1 = reduce_to_single_digit(abs(so_ngay_sinh - so_thang_sinh))
        thu_thach_2 = reduce_to_single_digit(abs(so_ngay_sinh - so_nam_sinh))
        thu_thach_3 = reduce_to_single_digit(abs(so_nam_sinh - so_thang_sinh))
        thu_thach_4 = reduce_to_single_digit(abs(thu_thach_1 - thu_thach_2))

        return {
            'so_chu_dao': so_chu_dao,
            'so_thai_do': so_thai_do,
            'so_ngay_sinh': so_ngay_sinh,
            'so_no_nghiep': self._karmic_debts(birth_day, sum_birth_day, so_chu_dao),
            'so_nam_ca_nhan': so_nam_ca_nhan,
            'so_thang_ca_nhan': reduce_to_single_digit(so_nam_ca_nhan + timezone.now().month),
            'tuoi_dinh_cao_1': tuoi_dinh_cao_1,
            'tuoi_dinh_cao_2': tuoi_dinh_cao_1 + 9,
            'tuoi_dinh_cao_3': tuoi_dinh_cao_1 + 18,
            'tuoi_dinh_cao_4': tuoi_dinh_cao_1 + 27,
            'dinh_cao_1': dinh_cao_1,
            'dinh_cao_2': dinh_cao_2,
            'dinh_cao_3': reduce_to_single_digit(dinh_cao_1 + dinh_cao_2),
            'dinh_cao_4': reduce_to_single_digit(so_thang_sinh + so_nam_sinh),
            'thu_thach_1': thu_thach_1,
            'thu_thach_2': thu_thach_2,
            'thu_thach_3': thu_thach_3,
            'thu_thach_4': thu_thach_4,
        }

    @staticmethod
    def _karmic_debts(birth_day, sum_birth_day, so_chu_dao):
        candidates = [
            next((x for x in KARMIC_DEBTS if x.startswith(birth_day[0] + birth_day[1])), ''),
            next((x for x in KARMIC_DEBTS if x.startswith(str(sum_birth_day))), ''),
            next((x for x in KARMIC_DEBTS if x.startswith(str(so_chu_dao))), ''),
        ]
        return [debt for debt in candidates if debt]

    @staticmethod
    def _name_numbers(full_name, so_chu_dao):
        """Numbers derived from the full name and from the given name alone."""
        full_name = strip_accents(full_name).lower()
        parts = full_name.split()
        given_name = parts[len(parts) - 1]

        full_total, full_vowels, full_consonants, values, _ = letter_values(full_name)
        so_su_menh = reduce_keeping_master(full_total)

        name_total, _name_vowels, _name_consonants, _, the_nhan_dang = letter_values(given_name)

        return {
            'so_su_menh': so_su_menh,
            'so_linh_hon': reduce_keeping_master(full_vowels),
            'so_nhan_cach': reduce_keeping_master(full_consonants),
            'so_truong_thanh': reduce_keeping_master(so_su_menh + so_chu_dao),
            'so_phat_trien': reduce_keeping_master(name_total),
            # `mode` needs at least one value; a name with no ASCII letters
            # would otherwise raise and surface as a bare 400.
            'so_noi_cam': mode(values) if values else 0,
            'the_nhan_dang': the_nhan_dang,
        }
