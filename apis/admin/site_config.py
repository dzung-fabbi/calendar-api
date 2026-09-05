"""Admin for the rating thresholds, bank details and membership transactions."""

from django.contrib import admin
from django.db import transaction
from django.utils import timezone
from django_object_actions import DjangoObjectActions, action

from apis.models import (
    BankConfig,
    BankTransaction,
    DateConfig,
    DirectionConfig,
    HoursConfig,
)


@admin.register(DateConfig)
class DateConfigAdmin(admin.ModelAdmin):
    list_display = ['id', 'very_good_from', 'good_from', 'ugly_from']


@admin.register(HoursConfig)
class HoursConfigAdmin(admin.ModelAdmin):
    list_display = ['id', 'very_good', 'good']


@admin.register(BankConfig)
class BankConfigAdmin(admin.ModelAdmin):
    list_display = ['account_number', 'account_holder', 'bank', 'branch']


@admin.register(BankTransaction)
class BankTransactionAdmin(DjangoObjectActions, admin.ModelAdmin):
    list_display = ['user', 'code', 'status']
    list_select_related = ['user']

    @action(
        label="Hoàn thành",
        description="Đánh dấu giao dịch hoàn thành và kích hoạt tài khoản",
    )
    def make_done(modeladmin, request, queryset):
        """Complete the selected transactions and upgrade their accounts.

        The membership upgrade never actually ran before: the guard was written
        `hasattr('profile', el.user)`, which tests the string for an attribute
        named after a User object and is therefore always False. Arguments are
        the right way round now, and the whole action is atomic so a failure
        part-way cannot mark transactions paid without upgrading the accounts.
        """
        with transaction.atomic():
            for el in queryset.select_related('user'):
                if hasattr(el.user, 'profile'):
                    profile = el.user.profile
                    profile.is_free = 1
                    profile.expiry_datetime = timezone.now().date()
                    profile.save()
            queryset.update(status=1)

    changelist_actions = ('make_done',)


@admin.register(DirectionConfig)
class DirectionConfigAdmin(admin.ModelAdmin):
    list_display = ['id', 'value']
