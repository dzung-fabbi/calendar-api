"""The pure half of the daily appointment reminder -- no ORM, no network.

`management/commands/remind_appointment_date.py` owns the queries and the
sending; this module is the arithmetic and the wording, so it is testable on
`SimpleTestCase` and obeys `docs/code-standards.md` -> Layering.
"""

import datetime as dt

TITLE = 'Sắp đến hạn lịch hẹn'

# Vietnam has no DST, so a fixed offset is exact. `settings.TIME_ZONE` is UTC
# with `USE_TZ=True`: a cron firing before 07:00 Vietnam time would otherwise
# compute *yesterday* and send every reminder a day off.
VN_TZ = dt.timezone(dt.timedelta(hours=7))


def today_vn():
    """Today's date in Vietnam, independent of the server's timezone."""
    return dt.datetime.now(VN_TZ).date()


def days_left(appointment_date, today):
    return (appointment_date - today).days


def message_body(name, appointment_date, today):
    """`"Còn 3 ngày nữa đến hạn: Đăng kiểm xe (01/10/2026)."`, or on the day
    itself `"Hôm nay đến hạn: Đăng kiểm xe (01/10/2026)."`.
    """
    when = appointment_date.strftime('%d/%m/%Y')
    left = days_left(appointment_date, today)
    if left <= 0:
        return 'Hôm nay đến hạn: {} ({}).'.format(name, when)
    return 'Còn {} ngày nữa đến hạn: {} ({}).'.format(left, name, when)


def push_data(appointment_id, appointment_date):
    """The FCM `data` payload -- strings only, that is what FCM accepts."""
    return {
        'type': 'appointment',
        'appointment_id': str(appointment_id),
        'date': appointment_date.isoformat(),
    }
