# Code Review: /api/appointment-date save + daily FCM reminder

Date: 2026-09-10. Plan: `plans/260910-1823-appointment-date-fcm-reminder/plan.md` (7/7 phases done).
Stack: Django 3.1 / DRF 3.14 / MySQL 5.7 (tests on real MySQL via `scripts/run-tests.sh`; 966 OK per lead).

## Scope
- Modified: `apis/serializers/booking.py`, `apis/views/booking.py`, `apis/models/__init__.py`,
  `apis/management/commands/remind_appointment_date.py`, `apis/tests/{test_management_commands,test_security}.py`,
  snapshots, `djangopj/settings.py` (comment), 5 docs.
- New: `apis/models/appointment_reminder_log.py`, `apis/migrations/0076_appointment_reminder_log.py`,
  `apis/selectors/appointment_remind.py`, `apis/services/appointment_remind.py`,
  `apis/management/commands/_appointment_reminder_log.py`, `apis/tests/test_appointment_date_api.py`.
- LOC: largest file 187 (test), 139 (view), 128 (command). All < 200.
- Cross-app import `apis -> giapha` (fcm / DeviceToken / active_tokens_for): sanctioned, not flagged.

## Overall
Solid. Ownership fixed properly, validation moved to serializer, batch job mirrors the proven giỗ job
shape 1:1, tests cover window boundaries / dedup / retry / dead-token / budget on real MySQL.
No Critical or High findings. Two Medium, rest Low/informational.

## Verified OK (asked-for focus points)
- **MySQL `DATE - INTERVAL MICROSECOND`**: Django 3.1 compiles `F('date') - F('before_days')` to
  `(date - INTERVAL before_days MICROSECOND)` -> DATETIME at 00:00:00. Compared with DATE param `today`,
  MySQL casts to DATETIME midnight, so `<=` (and old `=`) are exact. `before_days=0` -> `date 00:00:00 <= today`
  correct; NULL `date`/NULL result excluded. Tests exercise offsets 3,2,1,0 and D-4 / D+1 on MySQL.
- **Timezone**: `today_vn()` fixed UTC+7, `sent_on` keyed to VN date; cron `0 0 UTC` = 07:00 VN matches giỗ entry.
- **Null user / null date / past date**: excluded by `user__isnull=False, date__gte=today` (`selectors/appointment_remind.py:29`).
- **DRF `WholeDaysField`**: `default=timedelta` -> `required=False`, callable default -> 0 days; range check on int
  *before* `timedelta` conversion (correct — `min_value/max_value` validators would compare timedelta to int);
  `max_days` passed as kwarg so `Field.__deepcopy__` works; `1.5`, `'3 00:00:00'`, `'abc'`, `-1`, `366` -> 400 (tested).
- **Security**: `filter(user=user, id__in=...)` (`views/booking.py:66`); one 400 message for missing vs foreign id
  (no existence oracle); message echoes only caller-supplied ints; `BadRequestException` -> `{"detail": ...}` as docs say.
  No raw SQL. Logs/`error` column store FCM result codes, never tokens. GET scoped to `request.user`.
- **Layering**: `services/appointment_remind.py` pure (dt only); reads in selectors; ORM writes in
  `_appointment_reminder_log.py`; savepoint around `IntegrityError` per code-standards.
- **Migration 0076** matches model state (fields, `unique_together`, `db_table`, verbose names).
- **Plan**: all 7 phases `done`, file list matches diff.

## Medium
**M1. Concurrent runs double-push; `except IntegrityError` effectively unreachable.**
`_appointment_reminder_log.py:41-56`. Flow is read `sent_today` -> push -> `update_or_create`. Two overlapping
runs (cron overlap / manual re-run) both see no `sent` row, both push. `update_or_create` -> `get_or_create`
swallows the racing IntegrityError internally and re-`get`s, so the second run just overwrites and *also*
counts `sent += 1`. Comment "A concurrent run claimed this pair" (line 53) describes behaviour that does not
happen. Same latent pattern as `giapha/_gio_reminder_log.py:57` (parity, pre-existing). Risk low at 1 cron/day.
Fix options: (a) claim-before-send — `create(status='pending')` inside savepoint, IntegrityError -> skip, then
send and update status; (b) `flock -n` in the cron line; (c) at minimum correct the comment.

**M2. Legacy out-of-range `before_days` rows break round-trip and are silently never reminded.**
Old view accepted any int (`timedelta(days=int(...))`, no bound). A row with e.g. `before_days=99999d`:
GET renders `99999` (`serializers/booking.py:46`), client re-posting its own list gets 400 on a row it never
edited; and in MySQL `DATE_SUB` overflow -> NULL -> excluded from reminders with no signal. Fix: `RunPython`
in 0076 (or a one-off before deploy) clamping `before_days` to `0..365` days; or at least run
`SELECT COUNT(*) FROM appointment_dates WHERE before_days > 365*86400*1e6 OR before_days < 0` on prod first.

## Low
- **L1** `remind_appointment_date.py:11` docstring: `collect_due` "returns `(jobs, skipped)`" — actual is 3-tuple `(jobs, skipped, due)`.
- **L2** Duplicate `id` in one batch (`views/booking.py:62-90`): same instance mutated twice, appended twice to
  `updates`; last wins silently, response has fewer rows than posted. Consider 400 on duplicate ids.
- **L3** Ownership read (`views/booking.py:65-68`) is outside `transaction.atomic()` (line 97). Same-user
  concurrent POST deleting rows in between makes `bulk_update` a silent no-op. No security impact; move the
  read inside the atomic block (optionally `select_for_update()`).
- **L4** No cap on batch length — a user can `bulk_create` unbounded rows per request (pre-existing). Consider a
  max list size (e.g. 200) in the view or `ListSerializer(max_length=...)`.
- **L5** `AppointmentReminderLog` grows 1 row/appointment/day (up to 366 per appointment), no pruning. Fine now;
  note for ops (`DELETE ... WHERE sent_on < today - 30d` cron later).
- **L6** Docs vs code: `code-standards.md:31-33` says import sites are the 3 code modules and "nothing else
  crosses", but `apis/tests/test_management_commands.py:20-21` also imports `giapha`. Add "and its tests".
  `codebase-summary.md` lists the two test files but not the new modules (`selectors/appointment_remind.py`,
  `services/appointment_remind.py`, `models/appointment_reminder_log.py`, `_appointment_reminder_log.py`, migration 0076).
- **L7** `before_days: null` -> 400 (`allow_null=False`) while omitted -> 0. Acceptable; docs say only "mặc định 0".
  Either document null -> 400 or accept null as 0.
- **L8** `.annotate(remind_on=...)` puts an unused DATETIME column in SELECT (Django 3.1 has no `.alias()`).
  Harmless.
- **L9** POST `.delete()` now Python-cascades to `reminder_logs` (+2 queries/POST). A client that recreates rows
  without ids gets fresh ids -> same-day dedup lost -> a manual cron re-run that day pushes again. Ids
  round-trip per `test_reposting_the_response_round_trips`, so acceptable.
- **L10** Doc/comment "one write per push attempted" (`remind_appointment_date.py:19-20`, system-architecture):
  `update_or_create` is savepoint + `SELECT ... FOR UPDATE` + INSERT/UPDATE (3+ statements), plus a
  `DeviceToken` UPDATE when dead tokens appear. Conceptually one write; wording only.

## Positive
- Serializer now the single parse point; view never touches `request.data` after `is_valid()`.
- Whole-batch 400 instead of silent drop + delete — real data-loss fix.
- `failed` does not block retry; `{}` vs `ERROR_NETWORK` distinction honoured exactly as `fcm.py` documents.
- Query budget pinned in tests (1 query quiet day, 3 reads before first send).
- Snapshot goldens re-recorded alongside the change, diff self-documenting.
- `today_vn` duplicated rather than imported — follows decoupling rule where not sanctioned.

## Recommended actions (priority)
1. M2: add clamp `RunPython` to 0076 or verify prod data before deploy.
2. M1: fix comment at `_appointment_reminder_log.py:52-56`; optionally `flock -n` in cron line in deployment-guide.
3. L1, L6: docstring + docs touch-ups (5 min).
4. L2/L3/L4: optional hardening of POST (dup ids, atomic read, batch cap).

## Metrics
- Tests: 966 OK (per lead; not rerun). New tests: 16 command + 2 service + 8 API.
- Lint: pyflakes/flake8 not installed locally; `py_compile` clean on all changed .py files.
- File size rule: all < 200 lines.
- Query budget: GET appointment-date already in `test_query_counts.py`; POST not budgeted (not a new endpoint).

## Unresolved questions
1. Does prod `appointment_dates` contain `before_days` outside 0..365 or NULL-dated rows? (decides M2 urgency)
2. Is overlap of two `remind_appointment_date` runs realistic on 13.212.105.46 (manual re-runs while cron runs)? (decides M1 fix vs comment-only)
3. Should `before_days: null` be accepted as 0 for lenient clients?
4. Retention policy for `appointment_reminder_logs`?
