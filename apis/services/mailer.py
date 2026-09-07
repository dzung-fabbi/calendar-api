"""Outbound email. Currently only the password-reset OTP.

I/O but no ORM, so this belongs in `services/` -- the same licence
`giapha/services/fcm.py` operates under (`docs/code-standards.md` ->
Layering: "The rule is 'no ORM', not 'no I/O'").

FAILURE POLICY: a send failure is logged and swallowed, never raised. Two
reasons, and the second is the important one:

  * A password-reset request that answers 500 tells the caller nothing useful
    and loses the code that was already committed.
  * `forgot-password` MUST answer identically whether or not the address
    belongs to an account. If a broken mail server produced a 500 for real
    addresses and a 200 for unknown ones, the error itself would become an
    account-enumeration oracle.

THE CODE IS NEVER LOGGED. It is a live credential for as long as it is valid;
`logger.exception` here would put it in the log of every failed send.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

SUBJECT = 'Mã đặt lại mật khẩu'

BODY = """Xin chào,

Mã đặt lại mật khẩu của bạn là: {code}

Mã có hiệu lực trong {minutes} phút và chỉ dùng được một lần.

Nếu bạn không yêu cầu đặt lại mật khẩu, hãy bỏ qua email này -- mật khẩu hiện
tại của bạn không thay đổi.
"""


def send_password_reset_code(email, code, ttl_seconds):
    """Mail `code` to `email`. Returns True if the backend accepted it.

    The return value exists for tests and logging only -- no caller may branch
    on it in a way the client can observe, for the enumeration reason above.
    """
    try:
        send_mail(
            subject=SUBJECT,
            message=BODY.format(code=code, minutes=max(1, ttl_seconds // 60)),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except OSError:
        # smtplib raises SMTPException (an OSError subclass) and socket errors
        # are OSError too, so this covers refused connections, TLS failures and
        # the EMAIL_TIMEOUT expiring. Deliberately NOT `except Exception`
        # (`docs/code-standards.md` -> Errors): a TypeError in this module is a
        # bug and must still reach the logger as a 500.
        logger.warning('Không gửi được email đặt lại mật khẩu tới %s', email, exc_info=True)
        return False
    return True
