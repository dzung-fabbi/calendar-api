"""User-facing records: bookings, reminders, payment and membership."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save

from apis.models.choices import STATUS_TRANSACTION


class BookCalendar(models.Model):
    work = models.CharField(max_length=255)
    date = models.DateField()
    email = models.EmailField(max_length=255, null=True, blank=True)
    status = models.IntegerField(default=0)
    phone = models.CharField(max_length=255, null=True, blank=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Lịch đặt"
        verbose_name_plural = "Lịch đặt"


class AppointmentDate(models.Model):
    name = models.CharField(max_length=255)
    date = models.DateField(null=True)
    # `default=0` was an int, so any row created without an explicit value
    # blew up in the DurationField's DB adapter. `timedelta` is called to
    # produce a zero duration.
    before_days = models.DurationField(default=timedelta)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        db_table = "appointment_dates"
        verbose_name = "Lịch hẹn"
        verbose_name_plural = "Lịch hẹn"


class BankConfig(models.Model):
    account_number = models.CharField(max_length=255, verbose_name="Số tài khoản")
    account_holder = models.CharField(max_length=255, verbose_name="Chủ tài khoản")
    bank = models.CharField(max_length=255, verbose_name="Ngân hàng")
    branch = models.CharField(max_length=255, verbose_name="Chi nhánh", null=True, blank=True)
    qr_img = models.CharField(max_length=255, verbose_name="QR", null=True, blank=True)

    class Meta:
        verbose_name = "Ngân hàng"
        verbose_name_plural = "Ngân hàng"


class BankTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6, verbose_name="code")
    status = models.IntegerField(verbose_name="Trạng thái", default=0, choices=STATUS_TRANSACTION)

    class Meta:
        verbose_name = "Giao dịch"
        verbose_name_plural = "Giao dịch"


class UserProfile(models.Model):
    """Per-user data that does not fit on `auth.User`.

    `is_free`/`expiry_datetime` are BILLING internals and are deliberately not
    exposed by `apis/serializers/profile.py`; the three fields below are the
    only ones a user may read or write about themselves.

    NOT EVERY USER HAS A ROW. The signal at the bottom of this class only fires
    on creation, and the model arrived in migration 0055 -- so accounts older
    than that have none. Callers must use `hasattr(user, 'profile')` or
    `get_or_create`, never a bare `user.profile` (see
    `apis/admin/site_config.py.make_done`, which was fixed for exactly this).
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_free = models.IntegerField(verbose_name="Thành viên trả phí", default=0)
    expiry_datetime = models.DateField(verbose_name="Thời gian hết hạn", null=True)
    phone = models.CharField(verbose_name="Số điện thoại", max_length=20, blank=True, default='')
    birth_date = models.DateField(verbose_name="Ngày sinh", null=True, blank=True)
    # Client-supplied: the API stores a URL, it does not accept image bytes.
    # The serializer restricts the scheme to http/https -- an unchecked
    # `javascript:`/`data:` value here is echoed to every client that renders it.
    avatar_url = models.URLField(verbose_name="Ảnh đại diện", max_length=500, blank=True, default='')

    def create_user_profile(sender, instance, created, **kwargs):
        if created:
            profile, created = UserProfile.objects.get_or_create(user=instance)

    post_save.connect(create_user_profile, sender=User)
