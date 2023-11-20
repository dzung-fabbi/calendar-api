import string

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apis.models import ThanSatByYear, Sao, ThanSatByYearSao, ThanSatByMonth, SaoMonth1, SaoMonth2, SaoMonth3, \
    SaoMonth4, SaoMonth5, SaoMonth6, SaoMonth7, SaoMonth8, SaoMonth9, SaoMonth10, SaoMonth11, SaoMonth12


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        file = 'data/thủy thổ sơn.xlsx'
        with transaction.atomic():
            thansat_months = ThanSatByMonth.objects.all()

            for thansat_month in thansat_months:
                print('thansat_month.year', thansat_month.year.year)
                df = pd.read_excel(
                    io=file,
                    sheet_name='Năm {}'.format(string.capwords(thansat_month.year.year)),
                    header=None,
                )
                print('aaaa', thansat_month.year)
                df = df.to_records()
                for index, row in enumerate(df, 1):
                    sao_id = 1141

                    if sao_id is not None:
                        sao = Sao.objects.get(id=sao_id)
                        print('sao', sao.name)
                        direction = row[2].replace('\n', ' ').replace('  ', ' ').replace('.', '').strip().capitalize()
                        month = row[1].replace('\n', ' ').replace('  ', ' ').replace('.', '').strip().capitalize()
                        print('month', month)
                        month_arr = month.split(" ")
                        month1 = month_arr[1]

                        if direction == "Thủy":
                            direction = "Cấn"

                        print('month1', month1)
                        model = SaoMonth1
                        if int(month1) == 2:
                            model = SaoMonth2
                        if int(month1) == 3:
                            model = SaoMonth3
                        if int(month1) == 4:
                            model = SaoMonth4
                        if int(month1) == 5:
                            model = SaoMonth5
                        if int(month1) == 6:
                            model = SaoMonth6
                        if int(month1) == 7:
                            model = SaoMonth7
                        if int(month1) == 8:
                            model = SaoMonth8
                        if int(month1) == 9:
                            model = SaoMonth9
                        if int(month1) == 10:
                            model = SaoMonth10
                        if int(month1) == 11:
                            model = SaoMonth11
                        if int(month1) == 12:
                            model = SaoMonth12

                        print("model", model)

                        sao_month = model.objects.filter(
                            sao=sao,
                            than_sat_month=thansat_month,
                            direction=direction.capitalize()
                        ).first()
                        if sao_month is None:
                            model.objects.create(
                                sao=sao,
                                than_sat_month=thansat_month,
                                cung_son=sao.is_mountain,
                                direction=direction.capitalize()
                            )
