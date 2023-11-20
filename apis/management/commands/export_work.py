import string

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apis.models import ThanSatByYear, Sao, ThanSatByYearSao, ThanSatByMonth, SaoMonth1, SaoMonth2, SaoMonth3, \
    SaoMonth4, SaoMonth5, SaoMonth6, SaoMonth7, SaoMonth8, SaoMonth9, SaoMonth10, SaoMonth11, SaoMonth12, HiepKy

CAN = [
    'Giáp',
    'Ất',
    'Bính',
    'Đinh',
    'Mậu',
    'Kỷ',
    'Canh',
    'Tân',
    'Nhâm',
    'Quý',
]

CHI = [
    'Tý',
    'Sửu',
    'Dần',
    'Mão',
    'Thìn',
    'Tỵ',
    'Ngọ',
    'Mùi',
    'Thân',
    'Dậu',
    'Tuất',
    'Hợi',
]


def get_can_chi(jd):
    print('x', int((jd + 9) % 10))
    day_name = '{} {}'.format(CAN[int((jd + 9) % 10)], CHI[int((jd + 1) % 12)])
    return day_name

def universal_to_jd(D, M, Y):
    if Y > 1582 or (Y == 1582 and M > 10) or (Y == 1582 and M == 10 and D > 14):
        JD = 367 * Y - int(7 * (Y + int((M + 9) / 12)) / 4) - int(3 * (int((Y + (M - 9) / 7) / 100) + 1) / 4) + int(
            275 * M / 9) + D + 1721028.5
    else:
        JD = 367 * Y - int(7 * (Y + 5001 + int((M - 9) / 7)) / 4) + int(275 * M / 9) + D + 1729776.5
    return JD


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        with transaction.atomic():
            import pandas as pd

            dates = pd.date_range('2024-01-01', '2024-12-31', freq='D')
            arr_tmp = []
            for date in dates:
                jd = universal_to_jd(date.day, date.month, date.year)
                canchi = get_can_chi(jd).upper()
                print('canchi', canchi)
                hiep_ky = HiepKy.objects.filter(
                    month=date.month, lunar_day=canchi
                ).first()

                hiep_ky = hiep_ky.filter(Q(creator=owner) | Q(moderated=False))



            df = pd.DataFrame([[11, 21, 31], [12, 22, 32], [31, 32, 33]],
                              index=['one', 'two', 'three'], columns=['a', 'b', 'c'])

            print('hiepky', hiep_ky)
