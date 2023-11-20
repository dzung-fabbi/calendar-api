import string

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apis.models import ThanSatByYear, Sao, ThanSatByYearSao, ThanSatByMonth, SaoMonth1, SaoMonth2, SaoMonth3, \
    SaoMonth4, SaoMonth5, SaoMonth6, SaoMonth7, SaoMonth8, SaoMonth9, SaoMonth10, SaoMonth11, SaoMonth12


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        file = 'data/tietkhi.xlsx'
        with transaction.atomic():
            thansat_months = ThanSatByMonth.objects.all()

            for thansat_month in thansat_months:
                df = pd.read_excel(
                    io=file,
                    sheet_name='{}'.format(thansat_month.year),
                    header=None,
                )

                df = df.to_records()
                for index, row in enumerate(df, 1):
                    sao_id = None
                    if row[1].strip() == "Bính":
                        sao_id = 1265
                    if row[1].strip() == "Đinh":
                        sao_id = 1205
                    if row[1].strip() == "Ất":
                        sao_id = 1203

                    if sao_id is not None:
                        sao = Sao.objects.get(id=sao_id)
                        print('sao', sao.name)
                        direction = row[2].replace('\n', ' ').replace('  ', ' ').replace('.', '').strip().capitalize()
                        tietkhi = row[3].replace('\n', ' ').replace('  ', ' ').replace('.', '').strip().capitalize()
                        tietkhi = string.capwords(tietkhi)
                        model = SaoMonth1
                        if tietkhi in ["Kinh Trập", "Xuân Phân"]:
                            model = SaoMonth2
                        if tietkhi in ["Thanh Minh", "Cốc Vũ"]:
                            model = SaoMonth3
                        if tietkhi in ["Lập Hạ", "Tiểu Mãn"]:
                            model = SaoMonth4
                        if tietkhi in ["Mang Chủng", "Hạ Chí"]:
                            model = SaoMonth5
                        if tietkhi in ["Tiểu Thử", "Đại Thử"]:
                            model = SaoMonth6
                        if tietkhi in ["Lập Thu", "Xử Thử"]:
                            model = SaoMonth7
                        if tietkhi in ["Bạch Lộ", "Thu Phân"]:
                            model = SaoMonth8
                        if tietkhi in ["Hàn Lộ", "Sương Giáng"]:
                            model = SaoMonth9
                        if tietkhi in ["Lập Đông", "Tiểu Tuyết"]:
                            model = SaoMonth10
                        if tietkhi in ["Đại Tuyết", "Đông Chí"]:
                            model = SaoMonth11
                        if tietkhi in ["Tiểu Hàn", "Đại Hàn"]:
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
