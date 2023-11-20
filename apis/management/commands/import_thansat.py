import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apis.models import ThanSatByYear, Sao, ThanSatByYearSao, ThanSatByMonth, SaoMonth1, SaoMonth2, SaoMonth3, \
    SaoMonth4, SaoMonth5, SaoMonth6, SaoMonth7, SaoMonth8, SaoMonth9, SaoMonth10, SaoMonth11, SaoMonth12

lunar_day = [
    "Bính Ngọ",
    "Đinh Mùi",
    "Mậu Thân",
    "Tân Hợi",
    "Nhâm Tý",
    "Ất Mão",
    "Đinh Tỵ",
    "Mậu Ngọ",
    "Kỷ Mùi",
    "Canh Thân",
    "Tân Dậu",
    "Nhâm Tuất",
    "Quý Hợi"
]


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):

        file = 'data/Thần sát theo năm p1.xlsx'
        for x in lunar_day:
            # With a Sheet Name
            df = pd.read_excel(
                io=file,
                sheet_name=x,
                header=None,
            )
            with transaction.atomic():
                df = df.to_records()
                thansat_year = ThanSatByYear.objects.filter(year=x.upper()).first()
                for index, row in enumerate(df, 1):
                    if row[1] == 'Tên sao' or row[1] == 'Sao' or str(row[1]) == 'nan':
                        continue
                    if row[2] is None or str(row[2]) == 'nan':
                        continue
                    start = row[1].replace('\n', ' ').replace('  ', ' ').replace('.', '').strip().capitalize()
                    direction = row[2].strip()
                    if thansat_year:
                        sao = Sao.objects.filter(name=start.strip()).first()
                        if sao is None:
                            sao = Sao.objects.create(
                                name=start,
                                is_mountain=2,
                                good_ugly_stars=0
                            )

                        if direction.lower() == 'nam':
                            direction = 'Ly'
                        if direction.lower() == 'tây nam':
                            direction = 'Khôn'
                        if direction.lower() == 'tây':
                            direction = 'Đoài'
                        if direction.lower() == 'tây bắc':
                            direction = 'Càn'
                        if direction.lower() == 'bắc':
                            direction = 'Khảm'
                        if direction.lower() == 'đông bắc':
                            direction = 'Cấn'
                        if direction.lower() == 'đông':
                            direction = 'Chấn'
                        if direction.lower() == 'đông nam':
                            direction = 'Tốn'

                        ThanSatByYearSao.objects.create(
                            sao=sao,
                            than_sat_year=thansat_year,
                            cung_son=sao.is_mountain,
                            direction=direction.capitalize()
                        )

                thansat_month = ThanSatByMonth.objects.filter(year=thansat_year).first()
                for el in range(1, 13):
                    df = pd.read_excel(
                        io=file,
                        sheet_name='Tháng {} {}'.format(el, x),
                        header=None,
                    )

                    df = df.to_records()

                    for index, row in enumerate(df, 1):
                        if row[2] is None or str(row[2]) == 'nan':
                            continue
                        if row[1] == 'Tên sao' or row[1] == 'Sao' or str(row[1]) == 'nan':
                            continue
                        direction = row[2].strip()
                        start = row[1].replace('\n', ' ').replace('  ', ' ').replace('.', '').strip().capitalize()

                        if thansat_year:
                            sao = Sao.objects.filter(name=start.strip()).first()
                            if sao is None:
                                sao = Sao.objects.create(
                                    name=start,
                                    is_mountain=2,
                                    good_ugly_stars=0
                                )

                            if direction.lower() == 'nam':
                                direction = 'Ly'
                            if direction.lower() == 'tây nam':
                                direction = 'Khôn'
                            if direction.lower() == 'tây':
                                direction = 'Đoài'
                            if direction.lower() == 'tây bắc':
                                direction = 'Càn'
                            if direction.lower() == 'bắc':
                                direction = 'Khảm'
                            if direction.lower() == 'đông bắc':
                                direction = 'Cấn'
                            if direction.lower() == 'đông':
                                direction = 'Chấn'
                            if direction.lower() == 'đông nam':
                                direction = 'Tốn'

                            model = SaoMonth1
                            if el == 2:
                                model = SaoMonth2
                            if el == 3:
                                model = SaoMonth3
                            if el == 4:
                                model = SaoMonth4
                            if el == 5:
                                model = SaoMonth5
                            if el == 6:
                                model = SaoMonth6
                            if el == 7:
                                model = SaoMonth7
                            if el == 8:
                                model = SaoMonth8
                            if el == 9:
                                model = SaoMonth9
                            if el == 10:
                                model = SaoMonth10
                            if el == 11:
                                model = SaoMonth11
                            if el == 12:
                                model = SaoMonth12

                            model.objects.create(
                                sao=sao,
                                than_sat_month=thansat_month,
                                cung_son=sao.is_mountain,
                                direction=direction.capitalize()
                            )


