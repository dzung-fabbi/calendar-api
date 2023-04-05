from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apis.models import HiepKy, Sao, SaoHiepKy
import codecs

class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        hiepky = HiepKy.objects.all()
        for el in hiepky:
            good_stars = el.good_stars.split(',')
            if len(good_stars) > 0:
                for row in good_stars:
                    stars = row.replace('.', '').replace('\n', ' ').replace('   ', ' ').replace('  ', ' ').strip().capitalize()
                    tmp = Sao.objects.filter(name=stars).first()
                    if tmp is None:
                        tmp = Sao.objects.filter(name__icontains=stars).first()
                    if tmp:
                        SaoHiepKy.objects.create(hiepky=el, sao=tmp)

                    if tmp is None:
                        with codecs.open("sao.txt", "a", "utf-8-sig") as temp:
                            temp.write("{}\n".format(stars))

            ugly_stars = el.ugly_stars.split(',')
            if len(ugly_stars) > 0:
                for row in ugly_stars:
                    stars = row.replace('.', '').replace('\n', ' ').replace('   ', ' ').replace('  ', ' ').strip().capitalize()
                    tmp = Sao.objects.filter(name=stars).first()
                    if tmp is None:
                        tmp = Sao.objects.filter(name__icontains=stars).first()
                    if tmp:
                        SaoHiepKy.objects.create(hiepky=el, sao=tmp)

                    if tmp is None:
                        with codecs.open("sao.txt", "a", "utf-8-sig") as temp:
                            temp.write("{}\n".format(stars))
