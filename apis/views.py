from .models import *
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .serializers import *
from .exceptions import BadRequestException
from datetime import datetime
from itertools import chain

from operator import attrgetter


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
            tu_phuong_hung_thang = TuPhuongHung.objects.filter(year__iexact=year)

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
