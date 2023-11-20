import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apis.models import ThanSatByYear, Sao, ThanSatByYearSao, ThanSatByMonth, SaoMonth1, SaoMonth2, SaoMonth3, \
    SaoMonth4, SaoMonth5, SaoMonth6, SaoMonth7, SaoMonth8, SaoMonth9, SaoMonth10, SaoMonth11, SaoMonth12



class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        file = 'data/Dữ liệu bổ sung tất cả các tháng trong năm năm.xlsx'
        with transaction.atomic():
            thansat_month = ThanSatByMonth.objects.all()

            for thansat in thansat_month:
                for el in range(1, 13):
                    df = pd.read_excel(
                        io=file,
                        sheet_name='Tháng {} tất cả các năm'.format(el),
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

                        sao_month = model.objects.filter(
                            sao=sao,
                            than_sat_month=thansat,
                            direction=direction.capitalize()
                        ).first()
                        print('sao_month', sao_month)
                        if sao_month is None:
                            model.objects.create(
                                sao=sao,
                                than_sat_month=thansat,
                                cung_son=sao.is_mountain,
                                direction=direction.capitalize()
                            )




