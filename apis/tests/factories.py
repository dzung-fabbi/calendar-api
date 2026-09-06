"""Fixture builders for the API test-suite.

Built in Python rather than as a JSON fixture so the relationships (especially
the twelve hour/month through-tables) stay readable and can be reused by the
query-count tests, which need relations that are actually populated -- an empty
relation would make an N+1 fix look correct when it is not.
"""

import datetime as dt

from django.contrib.auth.models import User
from django.utils import timezone

from apis.constant import CAN_CHI
from apis.models import (
    AppointmentDate,
    BankConfig,
    CategoryStars,
    DateConfig,
    DirectionConfig,
    HiepKy,
    HourInDay,
    HoursConfig,
    QuyNhan,
    Sao,
    SaoHiepKy,
    SaoHour1,
    SaoHour2,
    SaoHour3,
    SaoMonth1,
    SaoMonth2,
    SaoMonth3,
    SaoMonth4,
    SaoMonth5,
    SaoMonth6,
    SaoMonth7,
    SaoMonth8,
    SaoMonth9,
    SaoMonth10,
    SaoMonth11,
    SaoMonth12,
    ThanSatByMonth,
    ThanSatByYear,
    ThanSatByYearSao,
    TietKhi,
    TuDaiCatThoi,
    TuDaiCatThoiSao,
)

SAO_MONTH_MODELS = [
    SaoMonth1, SaoMonth2, SaoMonth3, SaoMonth4, SaoMonth5, SaoMonth6,
    SaoMonth7, SaoMonth8, SaoMonth9, SaoMonth10, SaoMonth11, SaoMonth12,
]

# Request parameters the tests send. Kept here so the snapshot and query-count
# suites stay in agreement about what the fixture actually contains.
TIET_KHI = "Lập Xuân"
CAN_NGAY = "Giáp"
LUNAR_DAY = "GIÁP TÝ"
THAN_SAT_YEAR = "GIÁP THÌN"
MONTH = 1
WORK = "Cưới hỏi"
SHOULD_THINGS = "Cưới hỏi,Khai trương,Xuất hành"
NO_SHOULD_THINGS = "An táng"


def build_fixture():
    """Create the full reference dataset. Returns the objects tests need.

    Every row's primary key is pinned explicitly (via ``id=``). MySQL
    AUTO_INCREMENT counters are not transactional -- they survive the
    per-TestCase rollback -- so an implicit id here would depend on how many
    rows every *other* test (in this app or in ``giapha``, which shares the
    ``auth_user`` table) happened to insert first. ``assert_value_matches``
    golden files hardcode these ids, so an implicit id makes the value tests
    order-dependent instead of behaviour-dependent. Explicit ids sidestep the
    counter entirely: MySQL accepts an explicit value for an auto-increment
    column regardless of the counter's current position.
    """
    category = CategoryStars.objects.create(id=2, name="Hệ sao thử nghiệm")

    good_stars = [
        Sao.objects.create(
            id=5, name="Thiên Đức", property="Tốt mọi việc", good_ugly_stars=1,
            is_mountain=1, category=category, calendar=1, level=1.0,
            level_year=1.0, level_month=1.0, level_day=1.0, level_hours=1.0,
            point=10.0,
        ),
        # No category: exercises the None branch of SaoSerializer.get_category.
        Sao.objects.create(
            id=6, name="Nguyệt Đức", property="Tốt cho cưới hỏi", good_ugly_stars=1,
            is_mountain=2, category=None, calendar=2, level=2.0, point=8.0,
        ),
    ]
    ugly_stars = [
        Sao.objects.create(
            id=7, name="Thiên Cương", property="Xấu mọi việc", good_ugly_stars=2,
            is_mountain=1, category=category, calendar=1, level=1.0, point=-5.0,
        ),
        Sao.objects.create(
            id=8, name="Thọ Tử", property="Kỵ an táng", good_ugly_stars=2,
            is_mountain=2, category=None, calendar=1, level=1.0, point=-3.0,
        ),
    ]

    _build_hiep_ky(good_stars, ugly_stars)
    hour_in_day = _build_hour_in_day(good_stars, ugly_stars)
    tiet_khi = _build_tiet_khi()
    _build_quy_nhan()
    _build_tu_dai(good_stars)
    than_sat_year = _build_than_sat(good_stars, ugly_stars)
    _build_configs()

    user = User.objects.create_user(
        id=2, username="tester", email="tester@example.com", password="pw",
        first_name="Test", last_name="User",
    )
    AppointmentDate.objects.create(
        id=2, name="Giỗ tổ", date=dt.date(2026, 4, 18),
        before_days=dt.timedelta(days=3), user=user,
    )

    return {
        "category": category,
        "good_stars": good_stars,
        "ugly_stars": ugly_stars,
        "hour_in_day": hour_in_day,
        "tiet_khi": tiet_khi,
        "than_sat_year": than_sat_year,
        "user": user,
    }


def _build_hiep_ky(good_stars, ugly_stars):
    """One HiepKy row per can-chi for month 1, each with good and ugly stars.

    The real table holds 12 x 60 rows; having a whole month present is what
    makes the CalendarAPIView / DateGoodByWorkAPIView N+1s measurable.
    """
    for lunar_day in CAN_CHI:
        hiep_ky = HiepKy.objects.create(
            month=MONTH,
            lunar_day=lunar_day,
            should_things=SHOULD_THINGS,
            no_should_things=NO_SHOULD_THINGS,
        )
        for sao in good_stars + ugly_stars[:1]:
            SaoHiepKy.objects.create(hiepky=hiep_ky, sao=sao)


def _build_hour_in_day(good_stars, ugly_stars):
    hour_in_day = HourInDay.objects.create(lunar_day=LUNAR_DAY)
    # Stars spread over several hours, not just the first one.
    SaoHour1.objects.create(hour_1=hour_in_day, sao=good_stars[0])
    SaoHour1.objects.create(hour_1=hour_in_day, sao=ugly_stars[0])
    SaoHour2.objects.create(hour_2=hour_in_day, sao=good_stars[1])
    SaoHour3.objects.create(hour_3=hour_in_day, sao=ugly_stars[1])
    return hour_in_day


def _build_tiet_khi():
    year = timezone.now().year
    return TietKhi.objects.create(
        tiet_khi=TIET_KHI,
        start_time=timezone.make_aware(dt.datetime(year, 2, 4, 10, 0)),
        end_time=timezone.make_aware(dt.datetime(year, 2, 18, 10, 0)),
        year=str(year),
        gio_soc=timezone.make_aware(dt.datetime(year, 2, 4, 0, 0)),
    )


def _build_quy_nhan():
    QuyNhan.objects.create(
        can_ngay=CAN_NGAY, tiet_khi=TIET_KHI, hour="Tý",
        am_duong="Dương quý", quy_nhan="Sửu",
    )
    QuyNhan.objects.create(
        can_ngay=CAN_NGAY, tiet_khi=TIET_KHI, hour="Sửu",
        am_duong="Âm quý", quy_nhan="Tý",
    )


def _build_tu_dai(good_stars):
    tu_dai = TuDaiCatThoi.objects.create(
        hour="Tý", can_ngay=CAN_NGAY, tiet_khi=TIET_KHI,
    )
    for sao in good_stars:
        TuDaiCatThoiSao.objects.create(tudaicatthoi=tu_dai, sao=sao)
    return tu_dai


def _build_than_sat(good_stars, ugly_stars):
    than_sat_year = ThanSatByYear.objects.create(year=THAN_SAT_YEAR)
    ThanSatByYearSao.objects.create(
        sao=good_stars[0], than_sat_year=than_sat_year, direction="Khảm",
    )
    ThanSatByYearSao.objects.create(
        sao=ugly_stars[0], than_sat_year=than_sat_year, direction="Cấn",
    )

    than_sat_month = ThanSatByMonth.objects.create(year=than_sat_year)
    for index, model in enumerate(SAO_MONTH_MODELS):
        model.objects.create(
            sao=good_stars[index % len(good_stars)],
            than_sat_month=than_sat_month,
            direction="Khảm",
        )
        model.objects.create(
            sao=ugly_stars[index % len(ugly_stars)],
            than_sat_month=than_sat_month,
            direction="Cấn",
        )
    return than_sat_year


def _build_configs():
    # ids pinned for the same reason as build_fixture() above: these rows are
    # asserted by exact value in values_config.json.
    DateConfig.objects.create(
        id=2, very_good_from=1.5, good_from=1.0, ugly_from=0.5,
        factor_1=1.0, factor_2=2.0,
    )
    HoursConfig.objects.create(id=2, very_good=1.5, good=1.0, ugly=0.5)
    DirectionConfig.objects.create(id=2, value=1.0)
    BankConfig.objects.create(
        account_number="0123456789", account_holder="NGUYEN VAN A",
        bank="Vietcombank", branch="Hà Nội", qr_img="https://example.com/qr.png",
    )
