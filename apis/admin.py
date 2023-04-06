from django.contrib import admin
from django.forms import BaseInlineFormSet

from apis.models import Sao, HiepKy, SaoHiepKy


class SaoAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']


admin.site.register(Sao, SaoAdmin)


class DirectorInline(admin.TabularInline):
    model = HiepKy.sao.through
    extra = 0

class HiepKyAdmin(admin.ModelAdmin):
    list_display = ['id', 'month', 'lunar_day']
    inlines = [
        DirectorInline,
    ]


admin.site.register(HiepKy, HiepKyAdmin)