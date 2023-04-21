from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apis.models import Sao, TuDaiCatThoiSao, TuDaiCatThoi, ThanSatByYear, ThanSatByYearSao, ThanSatByMonth, SaoMonth1, \
    SaoMonth2, SaoMonth3, SaoMonth4, SaoMonth5, SaoMonth6, SaoMonth7, SaoMonth8, SaoMonth9, SaoMonth10, SaoMonth11, \
    SaoMonth12


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        than_sat_year = ThanSatByYear.objects.exclude(id=962)
        than_sat_year_962 = ThanSatByYear.objects.get(id=962)
        for el in than_sat_year:
            thansat_month_sao = than_sat_year_962.thansatbymonth_set.first()

            thansat_month_sao_create = ThanSatByMonth.objects.create(
                year_id=el.id,
                is_active=1
            )
            thansat_sao = thansat_month_sao.saomonth1_set.all()




            for row in thansat_sao:
                SaoMonth1.objects.create(
                    than_sat_month=thansat_month_sao_create,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )

                SaoMonth2.objects.create(
                    than_sat_month=thansat_month_sao,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )
                SaoMonth3.objects.create(
                    than_sat_month=thansat_month_sao,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )
                SaoMonth4.objects.create(
                    than_sat_month=thansat_month_sao,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )
                SaoMonth5.objects.create(
                    than_sat_month=thansat_month_sao,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )
                SaoMonth6.objects.create(
                    than_sat_month=thansat_month_sao,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )
                SaoMonth7.objects.create(
                    than_sat_month=thansat_month_sao,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )
                SaoMonth8.objects.create(
                    than_sat_month=thansat_month_sao,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )
                SaoMonth9.objects.create(
                    than_sat_month=thansat_month_sao,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )
                SaoMonth10.objects.create(
                    than_sat_month=thansat_month_sao,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )
                SaoMonth11.objects.create(
                    than_sat_month=thansat_month_sao,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )
                SaoMonth12.objects.create(
                    than_sat_month=thansat_month_sao,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )



            for row in thansat_sao:
                SaoMonth2.objects.create(
                    than_sat_month=thansat_month_sao_create,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )

            for row in thansat_sao:
                SaoMonth2.objects.create(
                    than_sat_month=thansat_month_sao_create,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )

            for row in thansat_sao:
                SaoMonth3.objects.create(
                    than_sat_month=thansat_month_sao_create,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )

            for row in thansat_sao:
                SaoMonth4.objects.create(
                    than_sat_month=thansat_month_sao_create,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )

            for row in thansat_sao:
                SaoMonth5.objects.create(
                    than_sat_month=thansat_month_sao_create,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )

            for row in thansat_sao:
                SaoMonth6.objects.create(
                    than_sat_month=thansat_month_sao_create,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )

            for row in thansat_sao:
                SaoMonth7.objects.create(
                    than_sat_month=thansat_month_sao_create,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )

            for row in thansat_sao:
                SaoMonth8.objects.create(
                    than_sat_month=thansat_month_sao_create,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )

            for row in thansat_sao:
                SaoMonth9.objects.create(
                    than_sat_month=thansat_month_sao_create,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )

            for row in thansat_sao:
                SaoMonth10.objects.create(
                    than_sat_month=thansat_month_sao_create,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )

            for row in thansat_sao:
                SaoMonth12.objects.create(
                    than_sat_month=thansat_month_sao_create,
                    sao_id=row.sao.id,
                    cung_son=row.cung_son,
                    direction=row.direction
                )
