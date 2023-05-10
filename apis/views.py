from django.db.models import Prefetch
from rest_framework import status
from rest_framework.permissions import AllowAny

from .constant import CAN_CHI
from .models import *
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import *
from .exceptions import BadRequestException
from datetime import datetime

from statistics import mode
import json


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


class CalendarAPIView(APIView):
    def get(self, request):
        try:
            arr_data = json.loads(request.GET.get('data'))
            data = []
            for day in arr_data:
                hiep_ky = HiepKy.objects.filter(
                    month=day['month'], lunar_day=day['lunar_day']
                ).first()

                if hiep_ky:
                    good_stars = SaoHiepKy.objects.filter(sao__good_ugly_stars=1, hiepky=hiep_ky).values_list(
                        "sao__name",
                        flat=True)
                    ugly_stars = SaoHiepKy.objects.filter(sao__good_ugly_stars=2, hiepky=hiep_ky).values_list(
                        "sao__name",
                        flat=True)
                    data.append({
                        'should_things': hiep_ky.should_things,
                        'no_should_things': hiep_ky.no_should_things,
                        'good_stars': ','.join(list(good_stars)),
                        'ugly_stars': ','.join(list(ugly_stars))
                    })
                else:
                    data.append({
                        'should_things': '',
                        'no_should_things': '',
                        'good_stars': '',
                        'ugly_stars': ''
                    })
            return Response({'data': data})
        except Exception:
            raise BadRequestException()


class HomeAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        tiet_khi = None
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


class ThanSatAPIView(APIView):
    def get(self, request):
        year = request.GET.get('year', None)
        than_sat_by_year = ThanSatByYear.objects.filter(year__iexact=year).first()
        than_sat_by_month = ThanSatByMonth.objects. \
            prefetch_related(
            'saomonth1_set',
            'saomonth2_set',
            'saomonth3_set',
            'saomonth4_set',
            'saomonth5_set',
            'saomonth6_set',
            'saomonth7_set',
            'saomonth8_set',
            'saomonth9_set',
            'saomonth10_set',
            'saomonth11_set',
            'saomonth12_set',
        ).filter(year__year__iexact=year).first()

        return Response(data={
            'than_sat_by_year': ThanSatByYearSerializer(than_sat_by_year, many=False).data,
            'than_sat_by_month': ThanSatByMonthSerializer(than_sat_by_month, many=False).data,
        })


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


class DateGoodByWorkAPIView(APIView):
    def get(self, request):
        work = request.GET.get('work', '')
        start_date = request.GET.get('start_date', None)
        can_chi_start = request.GET.get('can_chi_start', None)
        month_start = request.GET.get('month_start', None)
        month_end = request.GET.get('month_end', None)
        can_chi_start_up = can_chi_start.upper()
        end_date = request.GET.get('end_date', None)
        date_format = '%d/%m/%Y'
        start_date = datetime.strptime(start_date, date_format)
        end_date = datetime.strptime(end_date, date_format)
        delta = abs(end_date - start_date)
        index_of_start = CAN_CHI.index(can_chi_start_up)
        index_of_end = index_of_start + delta.days
        can_chi = CAN_CHI * (int(index_of_end / 60) + 1)
        arr_tmp = can_chi[index_of_start:index_of_end]
        hiep_ky = HiepKy.objects.filter(should_things__icontains=work, month__range=(month_start, month_end),
                                        lunar_day__in=arr_tmp)
        data = []
        for el in hiep_ky:
            good_stars = SaoHiepKy.objects.filter(sao__good_ugly_stars=1, hiepky=el).values_list("sao__name", flat=True)
            ugly_stars = SaoHiepKy.objects.filter(sao__good_ugly_stars=2, hiepky=el).values_list("sao__name", flat=True)
            is_good = self.get_day_good_ugly(el.should_things, el.no_should_things, ','.join(list(good_stars)),
                                             ','.join(list(ugly_stars)))
            if is_good["is_good"]:
                data.append({
                    "month": el.month,
                    "work": el.should_things,
                    "lunar_day": el.lunar_day,
                    "percent": is_good['percent'],
                    "text": is_good['text']
                })

        data = sorted(data, key=lambda x: x['percent'], reverse=True)
        return Response({'data': data})

    def get_day_good_ugly(self, good_thing, ugly_thing, good_star, ugly_star):
        if not good_thing or not good_star:
            return {
                "is_good": False
            }

        if not ugly_thing or not good_star:
            return {
                "is_good": False
            }

        percent = ((good_thing.split(',').__len__() / ugly_thing.split(',').__len__()) * 2 + good_star.split(
            ',').__len__() / ugly_star.split(',').__len__()) / 3
        if percent > 1.5:
            return {
                "is_good": True,
                "percent": percent,
                "text": "Ngày rất tốt"
            }

        if 1 <= percent <= 1.5:
            return {
                "is_good": True,
                "percent": percent,
                "text": "Ngày tốt"
            }

        if 1 > percent >= 0.5:
            return {
                "is_good": False,
                "percent": percent
            }
        return {
            "is_good": False
        }


class BookCalendarAPIView(APIView):
    def post(self, request, format=None):
        serializer = BookCalendarSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AppointmentDateAPIView(APIView):
    def get(self, request):
        user_id = request.GET.get('user_id', '')
        data = AppointmentDate.objects.filter(user_id=user_id)
        serializer = AppointmentDateSerializer(data, many=True)
        return Response({'data': serializer.data})

    def post(self, request, format=None):
        serializer = AppointmentDateSerializer(data=request.data, many=True)
        if serializer.is_valid():
            update_datas = []
            create_datas = []
            user_id = None
            ids = []
            for data in request.data:
                if data.get('id', None):
                    ids.append(data.get('id', None))
                    bulk_data = AppointmentDate.objects.get(id=data.get('id', None))
                    bulk_data.name = data.get('name', None)
                    bulk_data.date = data.get('date', None)
                    update_datas.append(bulk_data)
                    user_id = bulk_data.user_id
                else:
                    create_datas.append(AppointmentDate(**data))
            AppointmentDate.objects.exclude(id__in=ids).filter(user_id=user_id).delete()
            AppointmentDate.objects.bulk_update(update_datas, fields=['name', 'date'])
            AppointmentDate.objects.bulk_create(create_datas)
            return Response({
                'data': AppointmentDateSerializer(AppointmentDate.objects.filter(user_id=user_id), many=True).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
