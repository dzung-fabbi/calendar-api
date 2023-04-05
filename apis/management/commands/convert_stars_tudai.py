from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
import codecs
from apis.models import Sao, TuDaiCatThoiOld, TuDaiCatThoiSao, TuDaiCatThoi


class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def handle(self, *args, **options):
        tu_dai_cat_thoi_old = TuDaiCatThoiOld.objects.all()
        for el in tu_dai_cat_thoi_old:
            can_ngay_1 = el.can_ngay_1
            stars = can_ngay_1.replace('\n', ' ').replace('  ', ' ').strip().capitalize()
            tmp = Sao.objects.filter(name=stars).first()
            tu_dai_cat_thoi_new = TuDaiCatThoi.objects.create(
                hour=el.hour,
                tiet_khi=el.tiet_khi,
                can_ngay='Giáp',
            )
            if tmp is None:
                tmp = Sao.objects.filter(name__icontains=stars).first()
            if tmp:
                TuDaiCatThoiSao.objects.create(
                    sao=tmp,
                    tudaicatthoi=tu_dai_cat_thoi_new,
                )

            if tmp is None:
                with codecs.open("sao.txt", "a", "utf-8-sig") as temp:
                    temp.write("{}\n".format(stars))

            can_ngay_2 = el.can_ngay_2
            stars = can_ngay_2.replace('\n', ' ').replace('  ', ' ').strip().capitalize()
            tmp = Sao.objects.filter(name=stars).first()
            tu_dai_cat_thoi_new = TuDaiCatThoi.objects.create(
                hour=el.hour,
                tiet_khi=el.tiet_khi,
                can_ngay='Ất',
            )
            if tmp is None:
                tmp = Sao.objects.filter(name__icontains=stars).first()
            if tmp:
                TuDaiCatThoiSao.objects.create(
                    sao=tmp,
                    tudaicatthoi=tu_dai_cat_thoi_new,
                )

            if tmp is None:
                with codecs.open("sao.txt", "a", "utf-8-sig") as temp:
                    temp.write("{}\n".format(stars))

            can_ngay_3 = el.can_ngay_1
            stars = can_ngay_3.replace('\n', ' ').replace('  ', ' ').strip().capitalize()
            tmp = Sao.objects.filter(name=stars).first()
            tu_dai_cat_thoi_new = TuDaiCatThoi.objects.create(
                hour=el.hour,
                tiet_khi=el.tiet_khi,
                can_ngay='Bính',
            )
            if tmp is None:
                tmp = Sao.objects.filter(name__icontains=stars).first()
            if tmp:
                TuDaiCatThoiSao.objects.create(
                    sao=tmp,
                    tudaicatthoi=tu_dai_cat_thoi_new,
                )

            if tmp is None:
                with codecs.open("sao.txt", "a", "utf-8-sig") as temp:
                    temp.write("{}\n".format(stars))

            can_ngay_4 = el.can_ngay_4
            stars = can_ngay_4.replace('\n', ' ').replace('  ', ' ').strip().capitalize()
            tmp = Sao.objects.filter(name=stars).first()
            tu_dai_cat_thoi_new = TuDaiCatThoi.objects.create(
                hour=el.hour,
                tiet_khi=el.tiet_khi,
                can_ngay='Đinh',
            )
            if tmp is None:
                tmp = Sao.objects.filter(name__icontains=stars).first()
            if tmp:
                TuDaiCatThoiSao.objects.create(
                    sao=tmp,
                    tudaicatthoi=tu_dai_cat_thoi_new,
                )

            if tmp is None:
                with codecs.open("sao.txt", "a", "utf-8-sig") as temp:
                    temp.write("{}\n".format(stars))

            can_ngay_5 = el.can_ngay_5
            stars = can_ngay_5.replace('\n', ' ').replace('  ', ' ').strip().capitalize()
            tmp = Sao.objects.filter(name=stars).first()
            tu_dai_cat_thoi_new = TuDaiCatThoi.objects.create(
                hour=el.hour,
                tiet_khi=el.tiet_khi,
                can_ngay='Mậu',
            )
            if tmp is None:
                tmp = Sao.objects.filter(name__icontains=stars).first()
            if tmp:
                TuDaiCatThoiSao.objects.create(
                    sao=tmp,
                    tudaicatthoi=tu_dai_cat_thoi_new,
                )

            if tmp is None:
                with codecs.open("sao.txt", "a", "utf-8-sig") as temp:
                    temp.write("{}\n".format(stars))

            can_ngay_6 = el.can_ngay_6
            stars = can_ngay_6.replace('\n', ' ').replace('  ', ' ').strip().capitalize()
            tmp = Sao.objects.filter(name=stars).first()
            tu_dai_cat_thoi_new = TuDaiCatThoi.objects.create(
                hour=el.hour,
                tiet_khi=el.tiet_khi,
                can_ngay='Kỷ',
            )
            if tmp is None:
                tmp = Sao.objects.filter(name__icontains=stars).first()
            if tmp:
                TuDaiCatThoiSao.objects.create(
                    sao=tmp,
                    tudaicatthoi=tu_dai_cat_thoi_new,
                )

            if tmp is None:
                with codecs.open("sao.txt", "a", "utf-8-sig") as temp:
                    temp.write("{}\n".format(stars))

            can_ngay_7 = el.can_ngay_7
            stars = can_ngay_7.replace('\n', ' ').replace('  ', ' ').strip().capitalize()
            tmp = Sao.objects.filter(name=stars).first()
            tu_dai_cat_thoi_new = TuDaiCatThoi.objects.create(
                hour=el.hour,
                tiet_khi=el.tiet_khi,
                can_ngay='Canh',
            )
            if tmp is None:
                tmp = Sao.objects.filter(name__icontains=stars).first()
            if tmp:
                TuDaiCatThoiSao.objects.create(
                    sao=tmp,
                    tudaicatthoi=tu_dai_cat_thoi_new,
                )

            if tmp is None:
                with codecs.open("sao.txt", "a", "utf-8-sig") as temp:
                    temp.write("{}\n".format(stars))

            can_ngay_8 = el.can_ngay_8
            stars = can_ngay_8.replace('\n', ' ').replace('  ', ' ').strip().capitalize()
            tmp = Sao.objects.filter(name=stars).first()
            tu_dai_cat_thoi_new = TuDaiCatThoi.objects.create(
                hour=el.hour,
                tiet_khi=el.tiet_khi,
                can_ngay='Tân',
            )
            if tmp is None:
                tmp = Sao.objects.filter(name__icontains=stars).first()
            if tmp:
                TuDaiCatThoiSao.objects.create(
                    sao=tmp,
                    tudaicatthoi=tu_dai_cat_thoi_new,
                )

            if tmp is None:
                with codecs.open("sao.txt", "a", "utf-8-sig") as temp:
                    temp.write("{}\n".format(stars))

            can_ngay_9 = el.can_ngay_9
            stars = can_ngay_9.replace('\n', ' ').replace('  ', ' ').strip().capitalize()
            tmp = Sao.objects.filter(name=stars).first()
            tu_dai_cat_thoi_new = TuDaiCatThoi.objects.create(
                hour=el.hour,
                tiet_khi=el.tiet_khi,
                can_ngay='Nhâm',
            )
            if tmp is None:
                tmp = Sao.objects.filter(name__icontains=stars).first()
            if tmp:
                TuDaiCatThoiSao.objects.create(
                    sao=tmp,
                    tudaicatthoi=tu_dai_cat_thoi_new,
                )

            if tmp is None:
                with codecs.open("sao.txt", "a", "utf-8-sig") as temp:
                    temp.write("{}\n".format(stars))

            can_ngay_10 = el.can_ngay_10
            stars = can_ngay_10.replace('\n', ' ').replace('  ', ' ').strip().capitalize()
            tmp = Sao.objects.filter(name=stars).first()
            tu_dai_cat_thoi_new = TuDaiCatThoi.objects.create(
                hour=el.hour,
                tiet_khi=el.tiet_khi,
                can_ngay='Quý',
            )
            if tmp is None:
                tmp = Sao.objects.filter(name__icontains=stars).first()
            if tmp:
                TuDaiCatThoiSao.objects.create(
                    sao=tmp,
                    tudaicatthoi=tu_dai_cat_thoi_new,
                )

            if tmp is None:
                with codecs.open("sao.txt", "a", "utf-8-sig") as temp:
                    temp.write("{}\n".format(stars))

