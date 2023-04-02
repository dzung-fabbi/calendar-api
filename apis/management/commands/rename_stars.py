from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apis.models import Sao, TuDaiCatThoiOld, TuDaiCatThoiSao, TuDaiCatThoi


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        sao = Sao.objects.all()
        for el in sao:
            name = el.name.strip()
            el.name = name
            el.save()

