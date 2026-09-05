# Refactor report — logic + speed

Date: 2026-09-05. Branch: master. Nothing committed; all changes in working tree.

## Result

- 50 tests, all passing (`./scripts/run-tests.sh`). Repo had zero tests before.
- Query counts: calendar 90→2, get-date-good-by-work 121→3, than-sat 55→15, home 29→19.
- `makemigrations apis --check` clean; one deliberate migration (0072).
- Every endpoint except `/api/so-hoc` and `/api/get-user` returns byte-identical
  values to the pre-refactor code, proven by goldens recorded from HEAD in a
  throwaway git worktree.

## How behaviour-neutrality was proven

Recorded exact-value goldens by running the new test-suite against a worktree of
HEAD (original code), then imported those goldens into the refactored tree. Any
value drift fails the build. The two intended diffs are listed below.

## Speed

| Change | Effect |
|---|---|
| `CalendarAPIView`: OR'd Q + one bulk star query, index in memory | 3 queries/day → 2 total |
| `DateGoodByWorkAPIView`: can-chi→date map built once, bulk star fetch | 121 → 3 |
| `ThanSatAPIView`: `Prefetch(... select_related('sao','sao__category'))` on all 13 sets | 55 → 15 |
| `HourInDaySerializer` + `HomeAPIView`: prefetch 12 hour tables with `select_related('sao')` | 29 → 19 |
| Indexes on `TietKhi.start_time`, `(tiet_khi, start_time)`, `QuyNhan.can_ngay`, `TuDaiCatThoi.can_ngay` | migration 0072 |
| Numerology alphabet hoisted to module constant; `strip_accents` via `str.maketrans` | was rebuilt per request, O(n*m) scan |

Ceilings enforced by `test_query_counts.py`.

## Logic fixes

1. **Repeated digit reduction.** `get_sum` summed digits once, so `so_nam_sinh`
   came out as **10** for the test input — a two-digit "single-digit number".
   Now reduces fully. Knock-on: `thu_thach_2` 4→5, `thu_thach_3` 2→7.
2. **`thu_thach_4` duplicated `thu_thach_3`.** Now `|thu_thach_1 - thu_thach_2|`. 2→3.
3. **`DateConfig` wired in.** Thresholds (1.5/1/0.5) and weights (2/3) were
   hard-coded; the admin screen for them did nothing. Now drives `rate_day`.
   Defaults reproduce the old arithmetic exactly, so no value changed.
4. **`hasattr('profile', el.user)`** — arguments reversed, always False, so the
   admin "Hoàn thành" action never upgraded a membership. Fixed, made atomic.
5. **`DurationField(default=0)`** — an int, not a timedelta; creating an
   `AppointmentDate` without `before_days` crashed in the DB adapter. Found by
   the new tests.
6. **`remind_appointment_date`** built a queryset and discarded it. Now computes
   the due set correctly and logs it. Delivery still unspecified — see questions.
7. **`CAN_CHI`** hand-typed, contained a stray character in entry 34. Now derived
   from the stem/branch tables; a test asserts it equals the model choices.
8. **`TiInline`** autocompleted `hour_6` instead of `sao`; one hour inline had no
   autocomplete at all. Both gone with the inline factory.
9. **Blanket `except Exception`** replaced by up-front validation. Bad input now
   returns a 400 naming the parameter; real faults reach the logger as 500s.
   `/api/home` used to 500 on a missing parameter.
10. **Naive `datetime.now()`** under `USE_TZ=True` → `timezone.now()`.

### Deliberately NOT "fixed"

`get_day_good_ugly` tested `good_star` twice. The plan called for changing the
second to `ugly_star`. **That would have been wrong**: `''.split(',')` has
length 1, so a day with no ugly stars scores well today; requiring `ugly_star`
would have silently dropped the *best* days from the results. Verified, then
deduped the redundant condition instead. Test:
`test_day_with_no_ugly_stars_still_scores`.

## Security

| Issue | Fix |
|---|---|
| `UserSerializer` `fields='__all__'` on auth User, so `/api/get-user` returned the **password hash**, `is_superuser`, `is_staff`, permissions | Explicit whitelist |
| `AppointmentDate` POST: rows fetched by client id with no ownership filter, owner then read back off the row, so any user could read/overwrite/delete someone else's appointments | Scoped to `request.user`, `in_bulk` + ownership filter, atomic |
| Same endpoint: `AppointmentDate(**data)` let the caller set the `user` column | Explicit field construction |
| `BankAPIView` check-then-insert race, duplicate open transactions | `get_or_create` |
| `SECRET_KEY`, DB password, Facebook + Google OAuth secrets committed; `DEBUG=True`; `ALLOWED_HOSTS=[]` | Environment variables + `.env.example`; `DEBUG` off by default; missing key raises when not DEBUG |
| `CorsMiddleware` after `CommonMiddleware`; `CommonMiddleware` listed twice | Reordered, dedup |

4 ownership regressions + 1 exposure test in `test_security.py`.

**Action required: rotate the committed secrets.** They are in git history;
moving them to env does not revoke them.

## Structure

`models.py` 729 / `views.py` 565 / `serializers.py` 437 / `admin.py` 368 became
packages, every module under 200 lines. `SaoMonth1..12` collapsed onto an
abstract base; 25 admin inline classes and 12 month serializers now come from
factories. Wildcard imports removed (they were leaking the `month` /
`lunar_day` / `tiet_khi` choice tuples into the view namespace).

## Infrastructure

- `lunarcalendar` was imported at module scope but absent from
  `requirements.txt` — a clean build could not import the app at all.
- `FROM python:3` now resolves to a Python that Django 3.1 cannot run on.
  Pinned to `python:3.9-bullseye`.
- Test suite runs against **real MySQL**, not SQLite: the app depends on
  `utf8_unicode_ci` case-insensitivity (one `lunar_day` param is matched against
  both an upper-cased and a capitalised column). SQLite would have given false
  passes.

## Open questions

1. **`lunar_date` in `/api/get-date-good-by-work` looks wrong.** It returns e.g.
   `"2026-1-24"` — it converts the solar date back to lunar, so the month always
   equals the requested month and the field carries almost no information. The
   inline comment says it should return the solar date. Confirm before changing;
   it is what the frontend renders.
2. **`thu_thach_3` / `thu_thach_4` assignment.** Standard Pythagorean numerology
   puts `|C1-C2|` at position 3 and `|month-year|` at 4; this code has
   `|year-month|` at 3. Made the minimal change (fixed the duplicate at 4)
   without reordering. Confirm which convention you want.
3. **`so_chu_dao` and master numbers.** It uses non-master reduction, so a life
   path of 33 reduces to 6. Intended?
4. **`tiet_khi__icontains`** in `HomeAPIView` — does that column ever hold a
   comma-separated list, or is it standing in for `=`? Exact match would let the
   new index work.
5. **`remind_appointment_date` delivery** — email, push, or delete the command?
6. **`TIME_ZONE = 'UTC'`** with the MySQL container on `Asia/Tokyo`, for a
   Vietnamese app. Left untouched: switching shifts every serialized `TietKhi`
   datetime. Want it changed to `Asia/Ho_Chi_Minh`?
7. **`profile.expiry_datetime = now()`** in the admin upgrade action sets the
   membership to expire immediately. What is the intended period?
8. **71 migrations**, mostly auto-generated. Squash? Only safe if every
   environment is already at 0071.
