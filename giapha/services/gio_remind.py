"""The pure half of the daily giỗ reminder -- no ORM, no network.

`management/commands/remind_death_anniversary.py` keeps the queries and the
sending; everything here is arithmetic over rows already fetched, so it is
testable on `SimpleTestCase` and obeys `docs/code-standards.md` -> Layering.
"""

from collections import namedtuple

from giapha.services.gio import gio_occurrences_in_range, lunar_years_covering

TITLE = 'Sắp đến ngày giỗ'

# One person's giỗ plus its resolved audience. `recipients` is
# `{user_id: [token, ...]}`, filled in during collection so the sending half
# performs no per-recipient lookup of its own.
GioJob = namedtuple(
    'GioJob',
    'clan_id person_id ho_ten generation solar_date lunar_day lunar_month days_left recipients',
)


def message_body(job):
    """"Còn 3 ngày nữa là giỗ X (đời 4) — 5 tháng 2 âm lịch, nhằm 21/03/2026."

    `generation` is nullable (a person whose place in the tree was never
    computed, or one added below a gap in it), and "(đời None)" in a push
    notification is worse than dropping the clause entirely.
    """
    doi = ' (đời {})'.format(job.generation) if job.generation is not None else ''
    return 'Còn {} ngày nữa là giỗ {}{} — {} tháng {} âm lịch, nhằm {}.'.format(
        job.days_left, job.ho_ten, doi, job.lunar_day, job.lunar_month,
        job.solar_date.strftime('%d/%m/%Y'),
    )


def due_rows(rows, target):
    """`[(row, occurrence), ...]` for the persons whose giỗ lands on `target`.

    `rows` is what `selectors.gio.deceased_with_lunar_death` returns. The
    lunar death date is the source of truth -- a giỗ is never read off a
    stored solar date, because it moves every year.

    A row whose lunar date is unusable yields no occurrence and is skipped,
    per person: one bad row must not empty a clan's reminders.
    """
    lunar_years = lunar_years_covering(target, target)
    due = []
    for row in rows:
        occurrences = gio_occurrences_in_range(
            row['death_lunar_day'], row['death_lunar_month'], target, target,
            lunar_years=lunar_years,
        )
        if occurrences:
            due.append((row, occurrences[0]))
    return due
