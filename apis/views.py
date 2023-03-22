from .models import *
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .serializers import *
from .exceptions import BadRequestException
from datetime import datetime
from itertools import chain

from operator import attrgetter

from statistics import mode
import unicodedata


class TietkhiAPIView(APIView):
    def get(self, request):
        try:
            tiet_khi = TietKhi.objects.filter(
                tiet_khi=request.GET.get('tiet_khi'),
                start_time__year=datetime.now().year
            ).order_by('start_time').first()
            serializer = TietKhiSerializer(tiet_khi, allow_null=True)
            return Response({'data': serializer.data})
        except Exception:
            raise BadRequestException()


class HomeAPIView(APIView):
    def get(self, request):
        tiet_khi = None
        try:
            tiet_khi = TietKhi.objects.filter(start_time__lt=request.GET.get('lunar_date')).order_by(
                '-start_time'
            ).first()
            tiet_khi_serializer = TietKhiSerializer(tiet_khi, allow_null=True)
            hour_in_days = HourInDay.objects.filter(lunar_day=request.GET.get('lunar_day')).first()
            hour_in_days = HourInDaySerializer(hour_in_days, allow_null=True)
            quy_nhan_data = QuyNhan.objects.filter(
                can_ngay=request.GET.get('lunar_day').split()[0], tiet_khi__icontains=request.GET.get('tiet_khi')
            )
            quy_nhan_data = QuyNhanSerializer(quy_nhan_data, many=True)
            tu_dai_data = TuDaiCatThoi.objects.filter(tiet_khi__icontains=request.GET.get('tiet_khi'))
            tu_dai_data = TuDaiCatThoiSerializer(tu_dai_data, many=True)
            data = HiepKy.objects.filter(
                month=request.GET.get('month'), lunar_day=request.GET.get('lunar_day')
            ).first()
            serializer = HiepKySerializer(data, allow_null=True)
            return Response({'data': {
                'hiep_ky': serializer.data,
                'tiet_khi': tiet_khi_serializer.data,
                'hour_in_days': hour_in_days.data,
                'quy_nhan': quy_nhan_data.data,
                'tu_dai': tu_dai_data.data
            }})
        except Exception:
            raise BadRequestException()


class ThanSatAPIView(APIView):
    def get(self, request):
        try:
            year = request.GET.get('year', None)
            khai_son_tu_phuong_cat = KhaiSonTuPhuongCat.objects.filter(year__iexact=year)
            tam_nguyen_tu_bach = TamNguyenTuBach.objects.filter(is_active=True, year__iexact=year)
            cai_son_hoang_dao = CaiSonHoangDao.objects.filter(is_active=True, year__iexact=year).first()
            thong_thien_khieu = ThongThienKhieu.objects.filter(is_active=True, year__iexact=year).first()
            tau_ma_luc_nham = TauMaLucNham.objects.filter(is_active=True, year__iexact=year).first()
            khai_son_tu_phuong_hung = KhaiSonTuPhuongHung.objects.filter(is_active=True, year__iexact=year).first()
            khai_son_hung = KhaiSonHung.objects.filter(is_active=True, year__iexact=year).first()
            am_phu_thai_tue = AmPhuThaiTue.objects.filter(is_active=True, year__iexact=year).first()
            lap_huong_hung = LapHuongHung.objects.filter(is_active=True, year__iexact=year).first()
            tu_phuong_hung = TuPhuongHung.objects.filter(is_active=True, year__iexact=year).first()

            lap_huong_hung_thang = LapHuongHungThang.objects.filter(year__iexact=year)
            khai_son_hung_thang = KhaiSonHungThang.objects.filter(year__iexact=year)
            tu_phuong_hung_thang = TuPhuongHungThang.objects.filter(year__iexact=year)

            return Response(data={
                'khai_son_tu_phuong_cat': KhaiSonTuPhuongCatSerializer(khai_son_tu_phuong_cat, many=True).data,
                'tam_nguyen_tu_bach': TamNguyenTuBachSerializer(tam_nguyen_tu_bach, many=True).data,
                'cai_son_hoang_dao': CaiSonHoangDaoSerializer(cai_son_hoang_dao).data if bool(
                    cai_son_hoang_dao) else None,
                'thong_thien_khieu': ThongThienKhieuSerializer(thong_thien_khieu).data if bool(
                    thong_thien_khieu) else None,
                'tau_ma_luc_nham': TauMaLucNhamSerializer(tau_ma_luc_nham).data if bool(tau_ma_luc_nham) else None,
                'khai_son_tu_phuong_hung': KhaiSonTuPhuongHungSerializer(khai_son_tu_phuong_hung).data if bool(
                    khai_son_tu_phuong_hung) else None,
                'khai_son_hung': KhaiSonHungSerializer(khai_son_hung).data if bool(khai_son_hung) else None,
                'am_phu_thai_tue': AmPhuThaiTueSerializer(am_phu_thai_tue).data if bool(am_phu_thai_tue) else None,
                'lap_huong_hung': LapHuongHungSerializer(lap_huong_hung).data if bool(lap_huong_hung) else None,
                'tu_phuong_hung': TuPhuongHungSerializer(tu_phuong_hung).data if bool(tu_phuong_hung) else None,
                'lap_huong_hung_thang': LapHuongHungThangSerializer(lap_huong_hung_thang, many=True).data,
                'khai_son_hung_thang': KhaiSonHungThangSerializer(khai_son_hung_thang, many=True).data,
                'tu_phuong_hung_thang': TuPhuongHungThangSerializer(tu_phuong_hung_thang, many=True).data,
            })
        except Exception:
            raise BadRequestException()


class SoHocAPIView(APIView):
    def get(self, request):
        try:
            arr_nghiep = ['13/4', '14/5', '16/7', '19/1']
            birth_day = request.GET.get('birth_day')
            sum_birth_day = sum(int(x) for x in str(birth_day) if x.isdigit())
            so_chu_dao = self.get_sum(sum_birth_day)
            sum_ngay = int(birth_day[0]) + int(birth_day[1])
            so_ngay_sinh = self.get_sum(sum_ngay)
            sum_thang = int(birth_day[2]) + int(birth_day[3])
            so_thang_sinh = self.get_sum(sum_thang)
            so_nam_sinh = self.get_sum(sum_birth_day - sum_thang - sum_ngay)
            so_thai_do = self.get_sum(so_ngay_sinh + so_thang_sinh)
            so_nam_the_gioi = self.get_sum(datetime.now().year)
            so_nam_ca_nhan = self.get_sum(so_nam_the_gioi + so_thai_do)
            so_thang_ca_nhan = self.get_sum(so_nam_ca_nhan + datetime.now().month)
            tuoi_dinh_cao_1 = 36 - so_chu_dao
            tuoi_dinh_cao_2 = tuoi_dinh_cao_1 + 9
            tuoi_dinh_cao_3 = tuoi_dinh_cao_2 + 9
            tuoi_dinh_cao_4 = tuoi_dinh_cao_3 + 9
            dinh_cao_1 = self.get_sum(so_ngay_sinh + so_thang_sinh)
            dinh_cao_2 = self.get_sum(so_ngay_sinh + so_nam_sinh)
            dinh_cao_3 = self.get_sum(dinh_cao_1 + dinh_cao_2)
            dinh_cao_4 = self.get_sum(so_thang_sinh + so_nam_sinh)
            thu_thach_1 = self.get_sum(abs(so_ngay_sinh - so_thang_sinh))
            thu_thach_2 = self.get_sum(abs(so_ngay_sinh - so_nam_sinh))
            thu_thach_3 = self.get_sum(abs(so_nam_sinh - so_thang_sinh))
            thu_thach_4 = self.get_sum(abs(so_nam_sinh - so_thang_sinh))
            so_no_nghiep_1 = next((x for x in arr_nghiep if x.startswith(birth_day[0] + birth_day[1])), '')
            so_no_nghiep_2 = next((x for x in arr_nghiep if x.startswith(str(sum_birth_day))), '')
            so_no_nghiep_3 = next((x for x in arr_nghiep if x.startswith(str(so_chu_dao))), '')
            so_no_nghiep = []
            if so_no_nghiep_1:
                so_no_nghiep.append(so_no_nghiep_1)
            if so_no_nghiep_2:
                so_no_nghiep.append(so_no_nghiep_2)
            if so_no_nghiep_3:
                so_no_nghiep.append(so_no_nghiep_3)

            alphabet = {
                'a': {
                    'value': 1,
                    'is_vowel': True
                },
                'b': {
                    'value': 2,
                    'is_vowel': False
                },
                'c': {
                    'value': 3,
                    'is_vowel': False
                },
                'd': {
                    'value': 4,
                    'is_vowel': False
                },
                'e': {
                    'value': 5,
                    'is_vowel': True
                },
                'f': {
                    'value': 6,
                    'is_vowel': False
                },
                'g': {
                    'value': 7,
                    'is_vowel': False
                },
                'h': {
                    'value': 8,
                    'is_vowel': False
                },
                'i': {
                    'value': 9,
                    'is_vowel': True
                },
                'j': {
                    'value': 1,
                    'is_vowel': False
                },
                'k': {
                    'value': 2,
                    'is_vowel': False
                },
                'l': {
                    'value': 3,
                    'is_vowel': False
                },
                'm': {
                    'value': 4,
                    'is_vowel': False
                },
                'n': {
                    'value': 5,
                    'is_vowel': False
                },
                'o': {
                    'value': 6,
                    'is_vowel': True
                },
                'p': {
                    'value': 7,
                    'is_vowel': False
                },
                'q': {
                    'value': 8,
                    'is_vowel': False
                },
                'r': {
                    'value': 9,
                    'is_vowel': False
                },
                's': {
                    'value': 1,
                    'is_vowel': False
                },
                't': {
                    'value': 2,
                    'is_vowel': False
                },
                'u': {
                    'value': 3,
                    'is_vowel': True
                },
                'v': {
                    'value': 4,
                    'is_vowel': False
                },
                'w': {
                    'value': 5,
                    'is_vowel': False
                },
                'x': {
                    'value': 6,
                    'is_vowel': False
                },
                'y': {
                    'value': 7,
                    'is_vowel': False
                },
                'z': {
                    'value': 8,
                    'is_vowel': False
                }
            }

            full_name = self.strip_accents(request.GET.get('full_name')).lower()
            name = full_name.split()
            name = name[len(name) - 1]
            sum_full_name = 0
            sum_full_vowel = 0
            sum_full_consonant = 0
            arr_value = []
            for char in full_name:
                if char in alphabet:
                    if alphabet[char]['is_vowel']:
                        sum_full_vowel += alphabet[char]['value']
                    else:
                        sum_full_consonant += alphabet[char]['value']
                    sum_full_name += alphabet[char]['value']
                    arr_value.append(alphabet[char]['value'])
            so_linh_hon = self.get_sum_spec(self.get_sum_spec(sum_full_vowel))
            so_su_menh = self.get_sum_spec(self.get_sum_spec(sum_full_name))
            so_nhan_cach = self.get_sum_spec(self.get_sum_spec(sum_full_consonant))

            sum_name = 0
            sum_vowel = 0
            sum_consonant = 0
            the_nhan_dang = ''
            for char in name:
                if char in alphabet:
                    if alphabet[char]['is_vowel']:
                        if not the_nhan_dang:
                            the_nhan_dang = alphabet[char]['value']
                        sum_vowel += alphabet[char]['value']
                    else:
                        sum_consonant += alphabet[char]['value']
                    sum_name += alphabet[char]['value']
            so_linh_hon_name = self.get_sum_spec(self.get_sum_spec(sum_vowel))
            so_phat_trien = self.get_sum_spec(self.get_sum_spec(sum_name))
            so_dong_luc = self.get_sum_spec(self.get_sum_spec(sum_consonant))
            so_truong_thanh = self.get_sum_spec(so_su_menh + so_chu_dao)
            so_noi_cam = mode(arr_value)

            phone = request.GET.get('phone')
            so_dien_thoai = self.get_sum(self.get_sum(phone))
            return Response(data={
                'so_chu_dao': so_chu_dao,
                'so_thai_do': so_thai_do,
                'so_ngay_sinh': so_ngay_sinh,
                'so_su_menh': so_su_menh,
                'so_linh_hon': so_linh_hon,
                'so_nhan_cach': so_nhan_cach,
                'so_truong_thanh': so_truong_thanh,
                'so_phat_trien': so_phat_trien,
                'so_noi_cam': so_noi_cam,
                'so_no_nghiep': so_no_nghiep,
                'so_thieu': '',
                'the_nhan_dang': the_nhan_dang,
                'so_dien_thoai': so_dien_thoai,
                'so_nam_ca_nhan': so_nam_ca_nhan,
                'so_thang_ca_nhan': so_thang_ca_nhan,
                'tuoi_dinh_cao_1': tuoi_dinh_cao_1,
                'tuoi_dinh_cao_2': tuoi_dinh_cao_2,
                'tuoi_dinh_cao_3': tuoi_dinh_cao_3,
                'tuoi_dinh_cao_4': tuoi_dinh_cao_4,
                'dinh_cao_1': dinh_cao_1,
                'dinh_cao_2': dinh_cao_2,
                'dinh_cao_3': dinh_cao_3,
                'dinh_cao_4': dinh_cao_4,
                'thu_thach_1': thu_thach_1,
                'thu_thach_2': thu_thach_2,
                'thu_thach_3': thu_thach_3,
                'thu_thach_4': thu_thach_4,
            })
        except Exception:
            raise BadRequestException()

    def strip_accents(self, input_str):
        s1 = u'ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúýĂăĐđĨĩŨũƠơƯưẠạẢảẤấẦầẨẩẪẫẬậẮắẰằẲẳẴẵẶặẸẹẺẻẼẽẾếỀềỂểỄễỆệỈỉỊịỌọỎỏỐốỒồỔổỖỗỘộỚớỜờỞởỠỡỢợỤụỦủỨứỪừỬửỮữỰựỲỳỴỵỶỷỸỹ'
        s0 = u'AAAAEEEIIOOOOUUYaaaaeeeiioooouuyAaDdIiUuOoUuAaAaAaAaAaAaAaAaAaAaAaAaEeEeEeEeEeEeEeEeIiIiOoOoOoOoOoOoOoOoOoOoOoOoUuUuUuUuUuUuUuYyYyYyYy'
        s = ''
        input_str.encode('utf-8')
        for c in input_str:
            if c in s1:
                s += s0[s1.index(c)]
            else:
                s += c
        return s

    def get_sum(self, num):
        return sum(int(digit) for digit in str(num))

    def get_sum_spec(self, num):
        if num in [11, 22, 33]:
            return num
        return sum(int(digit) for digit in str(num))