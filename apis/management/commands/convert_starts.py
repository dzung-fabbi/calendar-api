from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apis.models import HiepKy, Sao, SaoHiepKy


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        hiepky = HiepKy.objects.all()
        for el in hiepky:
            good_stars = el.good_stars.split(',')
            if len(good_stars) > 0:
                for row_1 in good_stars:
                    tmp = Sao.objects.filter(name=row_1.strip().capitalize()).first()
                    if tmp:
                        SaoHiepKy.objects.create(hiepky=el, sao=tmp)

            ugly_stars = el.ugly_stars.split(',')
            if len(ugly_stars) > 0:
                for row_2 in ugly_stars:
                    stars_ugly = Sao.objects.filter(name=row_2.strip().capitalize()).first()
                    if stars_ugly:
                        SaoHiepKy.objects.create(hiepky=el, sao=stars_ugly)
