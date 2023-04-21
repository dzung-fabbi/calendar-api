from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apis.models import Sao, TuDaiCatThoiSao, TuDaiCatThoi, ThanSatByYear, ThanSatByYearSao


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        than_sat_year = ThanSatByYear.objects.exclude(id=962)
        than_sat_year_962 = ThanSatByYear.objects.get(id=962)
        for el in than_sat_year:
            thansat_sao = than_sat_year_962.thansatbyyearsao_set.all()
            for row in thansat_sao:
                print(row.sao)
                ThanSatByYearSao.objects.create(
                    than_sat_year=el,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction,
                )
