from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apis.models import HiepKy, Sao, SaoHiepKy, TuPhuongHungThang, ThanSatByMonth, LapHuongHungThang, KhaiSonHungThang, \
    KhaiSonTuPhuongCat, ThanSatByYear


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        khai_son_tu_phuong_cat = KhaiSonTuPhuongCat.objects.all()
        for el in khai_son_tu_phuong_cat:
            stars = el.star_name.replace('\n', ' ').replace('  ', ' ').strip()
            tmp = Sao.objects.filter(name__icontains=stars).first()
            if tmp:
                ThanSatByYear.objects.create(
                    sao=tmp,
                    year=el.year,
                    is_active=el.is_active,
                    direction=el.direction
                )

