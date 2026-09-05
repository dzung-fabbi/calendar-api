# Codebase Summary

## Endpoints

### apis/ (`/api/`, all public except noted)

| Route | View | Auth | Queries |
|---|---|---|---|
| `home` | `views/almanac.py` | public | 19 |
| `tiet-khi` | `views/almanac.py` | public | 1 |
| `calendar` | `views/almanac.py` | public | 2 (any batch size) |
| `than-sat` | `views/than_sat.py` | public | 15 |
| `so-hoc` | `views/numerology.py` | public | 0 |
| `get-date-good-by-work` | `views/good_day.py` | public | 3 |
| `get-config` | `views/account.py` | public | 3 |
| `book-calendar` | `views/booking.py` | public POST | - |
| `appointment-date` | `views/booking.py` | auth | 1 |
| `get-bank` | `views/booking.py` | auth | - |
| `get-user` | `views/account.py` | auth | 1 |

Query counts are enforced as ceilings by `apis/tests/test_query_counts.py`.

### giapha/ (`/api/gia-pha/`)

Routes: clan CRUD, person CRUD, marriages, invites, tree fetch, membership join, revisions.
All tree operations enforce the [**3-query contract**](#giapha-design-decisions). Route
prefix `/api/gia-pha/` is throttled on `/join` only (`giapha-join` scope: 10/hour).

**giỗ (death anniversary) endpoint:**

| Route | View | Auth | Queries | Window |
|---|---|---|---|---|
| `clans/{clan_id}/lich-gio` | `views/gio.py` | `IsClanMember` | 2 | next 12 months (default) |

Query params: `from=YYYY-MM-DD` and `to=YYYY-MM-DD` or `year=YYYY`. Max window 731 days
(2 calendar years). Response: `{items: [...], truncated: bool}`. Each item includes lunar
date (day, month, year), solar date, can-chi, days_until, and `adjusted` flag (day-30 lunar
falls back to day-29 in a 29-day month). Permission boundary: non-members receive 404.

**nhắc giỗ (reminder) endpoints — phase 6:**

| Route | Methods | View | Auth | Queries |
|---|---|---|---|---|
| `clans/{clan_id}/toi-la` | GET, PUT, DELETE | `views/member_binding.py` | `IsAuthenticated` + `IsClanMember` | - |
| `clans/{clan_id}/gio-follows` | GET | `views/gio_follow.py` | `IsAuthenticated` + `IsClanMember` | 5 (fixed) |
| `clans/{clan_id}/gio-follows/{person_id}` | PUT, DELETE | `views/gio_follow.py` | `IsAuthenticated` + `IsClanMember` | - |
| `devices` | POST, DELETE | `views/device.py` | `IsAuthenticated` **only** | - |

- `toi-la` -- the caller's own node in the tree (`ClanMember.person`). `GET` returns
  `{data: null}` when unbound. `PUT {person_id}` rejects a person of another clan, a
  deceased person, or one already claimed by another member (400 each). `DELETE` → 204.
- `gio-follows` `GET` returns `{items, bound, truncated}` — no `data` envelope. Each item:
  `person_id, ho_ten, thuy_hieu, generation, lunar {day, month}, followed, source`.
  `source` ∈ `truc-he` (direct-line ancestor) | `thu-cong` (manual add) | `da-bo`
  (explicitly removed). Listed rows are only the caller's ancestors plus anyone they
  overrode — not the whole clan's deceased. 5-query ceiling pinned by
  `assertNumQueries` in `tests/test_gio_follow_api.py`.
- `gio-follows/{person_id}` `PUT {enabled: bool}` upserts an override; `DELETE` removes it
  (back to the tree default — three states, not two). `PUT` rejects a person with no
  lunar day+month (400); `DELETE` deliberately does not, so a row stays removable after an
  editor clears the death date.
- `devices` is **not** clan-scoped: `IsClanMember` reads `view.kwargs['clan_id']`, which
  this route has not got, so it would 404 every caller. `POST {token, platform}` upserts
  keyed on `token` alone (201 new / 200 existing) and returns `{data: {platform,
  is_active}}` — never the token. `DELETE {token}` filters on `request.user` and answers
  204 either way.

## Query cost, before and after the refactor

| Endpoint | Before | After |
|---|---|---|
| `calendar` (30 days) | 90 | 2 |
| `get-date-good-by-work` | 121 | 3 |
| `than-sat` | 55 | 15 |
| `home` | 29 | 19 |

## Giapha services (Phase 5)

**Lunar calendar:** `services/vn_lunar.py` implements Vietnamese lunar calendar (UTC+7).
Port of Hồ Ngọc Đức's `amlich-hnd.js`. No external dependency. Supports 1800–2199.
Verified against original implementation and `lunarcalendar` (Chinese, UTC+8).

**Death anniversary (giỗ) rules:** `services/gio.py` computes giỗ occurrences. Handles
month-30→29 fallback with `adjusted` flag. Giỗ always observed in regular month, never
intercalary. One person can have two giỗ in a single solar year (drift across month boundary).

**Can-chi computation:** `services/can_chi.py` is a deliberate 10-line copy from
`apis/services/can_chi.py`. Duplication enforces package boundary (giapha shares no
imports from apis).

**Query optimization:** `selectors/gio.py` fetches all deceased with lunar death date
in one query. `services.gio` derives all occurrences in arithmetic (no N+1).

## Giapha reminders (Phase 6)

Push notifications for upcoming giỗ, with per-user follow control. Delivery to a real
device is **UNVERIFIED** — no Firebase project exists yet and every test mocks the FCM
layer; only the resolution, dedup and failure-handling logic is proven.

**New models** (migrations `0004`, `0005`):

| Model | Purpose |
|---|---|
| `ClanMember.person` | OneToOne, nullable, `SET_NULL`, `related_name='member_link'`. Binds a login to its own node. No backfill — a wrong guess would send another family's reminders. |
| `GioFollow(person, user, enabled)` | Override table. `unique_together ('person','user')`. Absence of a row = use the default. |
| `DeviceToken(user, token, platform, is_active, last_seen)` | `token` unique; `platform` ∈ ios/android/web. |
| `GioNotificationLog(person, user, solar_date, sent_at, status, error)` | `unique_together ('person','user','solar_date')` **is** the de-duplication mechanism. `status` ∈ sent/failed. |
| `Clan.gio_remind_before_days` | Lead time, default 3. |

**New modules:**

- `services/gio_follow.py` — pure. `ancestors(edges, person_id)` walks father AND mother
  backward; `followers_by_person(...)` resolves `{person_id: {user_id}}` at send time.
  Nothing is materialised, so editing the tree changes the follow set immediately and no
  re-sync job exists. Fails **OPEN** on a cycle (returns the partial set) — deliberately
  unlike `services/person_rules.descendants`, which fails CLOSED because it gates writes.
- `services/fcm.py` + `services/fcm_auth.py` — FCM **HTTP v1** (`google-auth==2.29.0` +
  `requests`, no `firebase-admin`; the legacy server key was switched off by Google in
  June 2024). TTL-cached OAuth token keyed on the service account. No ORM.
- `services/gio_remind.py` — pure message/date arithmetic (`GioJob`, `due_rows`,
  `message_body`).
- `selectors/gio_follow.py` — id-keyed dicts, never model instances; fixed query count.
- `selectors/person.clan_edges_all` — edges **including** soft-deleted rows, so a walk
  passes THROUGH a soft-deleted ancestor instead of stopping at them. Distinct from
  `clan_edges` on purpose; do not unify.
- `management/commands/remind_death_anniversary.py` + `_gio_reminder_log.py` (the two
  ORM writes; the leading underscore keeps Django's command discovery off it).

**Command query budget:** 1 query per clan with nothing due (an early `continue` after
`deceased_with_lunar_death`), ~5 on a day with a due giỗ. `test_remind_command.py` pins
`1 + 3` for three quiet clans. That ordering is load-bearing.

**Timezone:** the command uses `services.gio.today_vn()`, never `timezone.localdate()` —
`settings.TIME_ZONE` is `'UTC'` with `USE_TZ=True`.

## Test suites

**Total: 470 tests, 4 skipped** (50 `apis/` + 420 `giapha/`). The 4 skips are the tree
benchmarks, which need `BENCHMARK_TREE_PERFORMANCE=1`.

### apis/tests/
- `test_api_snapshots.py` -- freezes the **shape** (keys and types) of all 11 routes.
- `test_api_values.py` -- freezes **exact values** for deterministic endpoints.
  Golden files recorded from pre-refactor code, proving restructuring is behaviour-neutral.
- `test_query_counts.py` -- per-endpoint query ceiling; catches reintroduced N+1.
- `test_services.py` -- unit tests for `services/` (no database).
- `test_security.py` -- ownership and data-exposure regressions.
- `test_management_commands.py` -- `remind_appointment_date` (the `apis/` reminder;
  unrelated to `giapha/`'s `remind_death_anniversary`).

### giapha/tests/
- Query budgets asserted; 3-query `/tree` contract is verified per-test with `assertNumQueries`.
- Graph tests validate cycle rejection, soft-delete filtering, generation recomputation.
- Permission and invite tests validate 404 (not 403), expiry, role-grant patterns.
- Revision snapshot and restore tests with tree re-validation.
- `test_gio_follow_service.py` runs on `SimpleTestCase` (edge tuples, no database).
- `test_fcm_service.py` and `test_remind_command.py` patch `requests.post` /
  `_mint_token` / `send_multicast` in **every** test — the suite can never reach
  `fcm.googleapis.com`, and therefore never proves real delivery.

Run with `./scripts/run-tests.sh` (starts MySQL, builds test image, runs `manage.py test`).
Snapshots recorded on first run; `REWRITE_SNAPSHOTS=1` re-records after reviewed changes.

## Known remaining constraints

- **`/api/home` costs 19 queries**, twelve of them the per-hour through-tables.
  Reducing this further means collapsing `SaoHour1..12` into one table with an
  `hour` column -- a data migration, deliberately out of scope here.
- **`should_things__icontains`** in `get-date-good-by-work` cannot use an index.
  Acceptable at the table's size (12 months x 60 can-chi = 720 rows max).
- **`tiet_khi__icontains`** in `HomeAPIView` is used where an exact match looks
  intended; left as-is pending confirmation that the column never holds a list.
- **Django 3.1 is end-of-life.** The Dockerfile is pinned to Python 3.9 because
  3.1 does not run on 3.12+. An upgrade path is the next structural piece of work.
