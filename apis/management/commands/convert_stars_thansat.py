from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apis.models import HiepKy, Sao, SaoHiepKy, TuPhuongHungThang, ThanSatByMonth, LapHuongHungThang, KhaiSonHungThang


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        tu_phuong_hung_thang = TuPhuongHungThang.objects.all()
        for el in tu_phuong_hung_thang:
            stars = el.star_name.replace('\n', ' ').replace('  ', ' ').strip().capitalize()
            tmp = Sao.objects.filter(name=stars).first()
            if tmp:
                ThanSatByMonth.objects.create(
                    sao=tmp,
                    year=el.year,
                    is_active=el.is_active,
                    month_1=el.month_1.replace('\n', ' '),
                    month_2=el.month_2.replace('\n', ' '),
                    month_3=el.month_3.replace('\n', ' '),
                    month_4=el.month_4.replace('\n', ' '),
                    month_5=el.month_5.replace('\n', ' '),
                    month_6=el.month_6.replace('\n', ' '),
                    month_7=el.month_7.replace('\n', ' '),
                    month_8=el.month_8.replace('\n', ' '),
                    month_9=el.month_9.replace('\n', ' '),
                    month_10=el.month_10.replace('\n', ' '),
                    month_11=el.month_11.replace('\n', ' '),
                    month_12=el.month_12.replace('\n', ' ')
                )

        khai_son_hung_thang = KhaiSonHungThang.objects.all()
        for el in khai_son_hung_thang:
            stars = el.star_name.replace('\n', ' ').replace('  ', ' ').strip().capitalize()
            tmp = Sao.objects.filter(name=stars).first()
            if tmp:
                ThanSatByMonth.objects.create(
                    sao=tmp,
                    year=el.year,
                    is_active=el.is_active,
                    month_1=el.month_1.replace('\n', ' '),
                    month_2=el.month_2.replace('\n', ' '),
                    month_3=el.month_3.replace('\n', ' '),
                    month_4=el.month_4.replace('\n', ' '),
                    month_5=el.month_5.replace('\n', ' '),
                    month_6=el.month_6.replace('\n', ' '),
                    month_7=el.month_7.replace('\n', ' '),
                    month_8=el.month_8.replace('\n', ' '),
                    month_9=el.month_9.replace('\n', ' '),
                    month_10=el.month_10.replace('\n', ' '),
                    month_11=el.month_11.replace('\n', ' '),
                    month_12=el.month_12.replace('\n', ' ')
                )

        lap_huong_hung_thang = LapHuongHungThang.objects.all()
        for el in lap_huong_hung_thang:
            stars = el.star_name.replace('\n', ' ').replace('  ', ' ').strip().capitalize()
            tmp = Sao.objects.filter(name=stars).first()
            if tmp:
                ThanSatByMonth.objects.create(
                    sao=tmp,
                    year=el.year,
                    is_active=el.is_active,
                    month_1=el.month_1.replace('\n', ' '),
                    month_2=el.month_2.replace('\n', ' '),
                    month_3=el.month_3.replace('\n', ' '),
                    month_4=el.month_4.replace('\n', ' '),
                    month_5=el.month_5.replace('\n', ' '),
                    month_6=el.month_6.replace('\n', ' '),
                    month_7=el.month_7.replace('\n', ' '),
                    month_8=el.month_8.replace('\n', ' '),
                    month_9=el.month_9.replace('\n', ' '),
                    month_10=el.month_10.replace('\n', ' '),
                    month_11=el.month_11.replace('\n', ' '),
                    month_12=el.month_12.replace('\n', ' ')
                )
