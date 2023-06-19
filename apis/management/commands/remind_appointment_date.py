from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q, F
import datetime
from django.utils import timezone

from apis.models import AppointmentDate


class Command(BaseCommand):
    help = 'Remind appointment date'

    def handle(self, *args, **options):
        print(datetime.datetime.now())
        datas = AppointmentDate.objects.filter(date=datetime.datetime.now().date()+F('before_days'))
