from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apis.models import HiepKy, Sao, SaoHiepKy, HourInDay, SaoHour1, SaoHour2, SaoHour12, SaoHour11, SaoHour10, \
    SaoHour9, SaoHour8, SaoHour7, SaoHour6, SaoHour5, SaoHour4, SaoHour3


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        hours = HourInDay.objects.all()
        for el in hours:
            hours_1 = el.hour_1.replace('\r', '').split('\n')
            for row in hours_1:
                tmp = Sao.objects.filter(name=row.strip().capitalize()).first()
                if tmp:
                    SaoHour1.objects.create(hour_1=el, sao=tmp)

            hours_2 = el.hour_2.replace('\r', '').split('\n')
            for row in hours_2:
                tmp = Sao.objects.filter(name=row.strip().capitalize()).first()
                if tmp:
                    SaoHour2.objects.create(hour_2=el, sao=tmp)

            hours_3 = el.hour_3.replace('\r', '').split('\n')
            for row in hours_3:
                tmp = Sao.objects.filter(name=row.strip().capitalize()).first()
                if tmp:
                    SaoHour3.objects.create(hour_3=el, sao=tmp)

            hours_4 = el.hour_4.replace('\r', '').split('\n')
            for row in hours_4:
                tmp = Sao.objects.filter(name=row.strip().capitalize()).first()
                if tmp:
                    SaoHour4.objects.create(hour_4=el, sao=tmp)

            hours_5 = el.hour_5.replace('\r', '').split('\n')
            for row in hours_5:
                tmp = Sao.objects.filter(name=row.strip().capitalize()).first()
                if tmp:
                    SaoHour5.objects.create(hour_5=el, sao=tmp)

            hours_6 = el.hour_6.replace('\r', '').split('\n')
            for row in hours_6:
                tmp = Sao.objects.filter(name=row.strip().capitalize()).first()
                if tmp:
                    SaoHour6.objects.create(hour_6=el, sao=tmp)

            hours_7 = el.hour_7.replace('\r', '').split('\n')
            for row in hours_7:
                tmp = Sao.objects.filter(name=row.strip().capitalize()).first()
                if tmp:
                    SaoHour7.objects.create(hour_7=el, sao=tmp)

            hours_8 = el.hour_8.replace('\r', '').split('\n')
            for row in hours_8:
                tmp = Sao.objects.filter(name=row.strip().capitalize()).first()
                if tmp:
                    SaoHour8.objects.create(hour_8=el, sao=tmp)

            hours_9 = el.hour_9.replace('\r', '').split('\n')
            for row in hours_9:
                tmp = Sao.objects.filter(name=row.strip().capitalize()).first()
                if tmp:
                    SaoHour9.objects.create(hour_9=el, sao=tmp)

            hours_10 = el.hour_10.replace('\r', '').split('\n')
            for row in hours_10:
                tmp = Sao.objects.filter(name=row.strip().capitalize()).first()
                if tmp:
                    SaoHour10.objects.create(hour_10=el, sao=tmp)

            hours_11 = el.hour_11.replace('\r', '').split('\n')
            for row in hours_11:
                tmp = Sao.objects.filter(name=row.strip().capitalize()).first()
                if tmp:
                    SaoHour11.objects.create(hour_11=el, sao=tmp)

            hours_12 = el.hour_12.replace('\r', '').split('\n')
            for row in hours_12:
                tmp = Sao.objects.filter(name=row.strip().capitalize()).first()
                if tmp:
                    SaoHour12.objects.create(hour_12=el, sao=tmp)

