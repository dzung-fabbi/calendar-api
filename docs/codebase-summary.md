# Codebase Summary

> Account endpoints (`/api/auth/*`, `/api/me`) are documented in `docs/api-reference.md` → "Tài Khoản".
> Full request/response reference for `giapha/` (auth, error catalogue, per-endpoint fields, client gotchas): `docs/api-reference.md`. The table below is a map, not a contract.

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
| `me` (GET, PATCH) | `views/account.py` | auth | 1 / 5 |
| `auth/register` | `views/auth_register.py` | public POST | 8 |
| `auth/forgot-password` | `views/auth_password_reset.py` | public POST | 5 |
| `auth/verify-otp` | `views/auth_password_reset.py` | public POST | - |
| `auth/reset-password` | `views/auth_password_reset.py` | public POST | - |
| `auth/change-password` | `views/auth_password_change.py` | auth POST | 5 |
| `files/upload-url` | `views/file_upload.py` | public POST, throttled | 0 |
| `files/confirm` | `views/file_upload.py` | public POST, throttled | 0 |

Query counts are enforced as ceilings by `apis/tests/test_query_counts.py`.

### giapha/ (`/api/gia-pha/`)

Routes: clan CRUD, person CRUD, marriages, invites, tree fetch, membership join, revisions.
All tree operations enforce the [**3-query contract**](#giapha-design-decisions). Route
prefix `/api/gia-pha/` is throttled on `/join` only (`giapha-join` scope: 10/hour).

**auth endpoints (`djangopj/auth_token_views.py`, mounted at `/auth/` outside both apps):**

| Route | Methods | Auth |
|---|---|---|
| `/auth/token` | POST | `AllowAny` -- credentials are in the body (grants: `password`, `refresh_token`) |
| `/auth/revoke-token` | POST | `AllowAny` -- `client_id`/`client_secret`/`token` in the body |

Both accept form-encoded (`application/x-www-form-urlencoded`) or JSON bodies; the trailing
slash is optional. Neither runs an authenticator (`authentication_classes = ()`), so a stale
`Bearer` header cannot 401 a token refresh. Username/password is the only login flow.

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

**máy tính xưng hô (kinship calculator) — phase 7:**

| Route | Methods | View | Auth | Queries |
|---|---|---|---|---|
| `clans/{clan_id}/xung-ho?a=&b=` | GET | `views/kinship.py` | `IsAuthenticated` + `IsClanMember` | 2 / 3 / 4 (see below) |

- **`a` is optional**; it defaults to the caller's own `ClanMember.person` binding (phase 6).
  `b` is required. An unbound caller who omits `a` gets **400** telling them to set
  `/toi-la` (never a guess). A stale binding gets its own 400 message, not "bad `a`".
  Non-integer id, id from another clan, or a soft-deleted person → 400. Non-members → 404.
- Response: `a_calls_b`, `b_calls_a` (each `{term, confident, reason}`), `common_ancestor`
  (`{id, ho_ten}` or `null`), `path` (`{a_up, b_up, side}`), `explain`.
  `path` is **always an object** — on any non-blood answer all three of its fields are
  `null`, the object itself is not.
- **No blood relation is HTTP 200 with `term: null`**, not an error. `reason` says which
  kind of "no word" it is; `confident` is `true` for "there is genuinely no link".
- `reason` is always a **machine-readable ASCII slug**; the Vietnamese wording for a
  reader is in `explain` only. Slugs: `khong_cung_huyet_thong`, `cung_mot_nguoi`,
  `thieu_birth_order`, `thieu_gioi_tinh`, `khong_co_tu_xung_ho_thong_dung`,
  `nhieu_hon_nhan_ngang_hang`, `ngoai_bang_tu_vung`.
- **Query budget — 2 common, 4 worst case** (each pinned by `assertNumQueries` in
  `tests/test_kinship_api.py` *alongside* the answer produced, so a count cannot pass
  vacuously on a 400):

  | Request | Queries |
  |---|---|
  | explicit `a`, pair has a blood link | 2 (cached role check + `clan_kinship_rows`) |
  | `a` omitted (binding lookup) | 3 |
  | no blood link (lazy `clan_spouse_pairs`) | 3 |
  | `a` omitted **and** no blood link — the ordinary request of a member who married in | 4 |

  The spec asked for ≤2; the two optional paths each cost one more, deliberately. Neither
  query grows with clan size.
- No model, no migration, no new setting. `clan_kinship_rows` is **exempt from
  `settings.MAX_CLAN_PERSONS`** on purpose — truncating rows would not degrade the answer,
  it would falsify it (a missing ancestor turns a real relative into
  `khong_cung_huyet_thong` with `confident: true`).

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

**Object storage:** `apis/services/storage.py` is a deliberate twin of `giapha/services/storage.py` for the
same reason -- same `S3_*` settings, same presign/head logic, minus `delete()` (which
`apis/` has no endpoint for). A behavioural fix in one needs the same fix in the other.

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

## Giapha kinship calculator (Phase 7)

"Máy tính xưng hô" — what two people in a clan call each other. **No model and no
migration**: the answer is computed from rows already in the tree.

**New modules** — every `services/kinship*` file is pure (no ORM, no `request`), so
`tests/test_kinship*.py` run on `SimpleTestCase`:

| Module | Owns |
|---|---|
| `services/kinship.py` | entry point `resolve_kinship(rows, a_id, b_id, spouses=None)`; picks blood vs marriage |
| `services/kinship_graph.py` | `ancestor_index` (BFS up, records depth/side/via), `best_common_ancestor`, `lowest_common_ancestor` |
| `services/kinship_blood.py` | the answer for two blood relatives; owns the response **shape** (`result`, `unrelated`, `EMPTY_PATH`) |
| `services/kinship_lookup.py` | facts → word: table widening, `is_elder`, `gender_of`, `resolve_term` |
| `services/kinship_terms.py` | blood vocabulary + `reason` slugs + `REASON_LABELS`. **Data only** |
| `services/kinship_affinal_terms.py` | in-law vocabulary, `MARRIED_IN_SUBSTITUTES`, `SPOUSE_TERMS`. **Data only** |
| `services/kinship_affinal.py` | the walk through a `Marriage` edge, both directions |
| `services/kinship_marriage_rows.py` | *which* marriage to answer through (`ranked_spouses_of`, `spouses_of`) |
| `services/kinship_explain.py` | the Vietnamese sentence; restates only facts passed in |
| `serializers/kinship.py`, `views/kinship.py` | response shape / HTTP |

**New selectors** (one query each, scalars/dicts only — the services are pure):

- `selectors/person.clan_kinship_rows(clan_id)` → `[{id, father_id, mother_id, birth_order,
  gioi_tinh, ho_ten}]`, non-deleted only. **Dicts, not tuples**, so it can gain a column
  without breaking a consumer.
- `selectors/marriage.clan_spouse_pairs(clan_id)` → `[(husband_id, wife_id, status, order)]`,
  both partners non-deleted, `ly_hon` excluded and **`goa` kept** (a widow stays her late
  husband's family's thím; a divorced wife does not). `status`/`order` travel with the pair
  because the ranking rule needs them.

`clan_edges` and `clan_edges_all` were **not** changed — see
`docs/system-architecture.md` → "Three edge shapes, on purpose".

**Vocabulary is Northern dialect (miền Bắc) only.** Elder sibling of *either* parent is
`bác`; `chú`/`cô` = father's younger brother/sister, `cậu`/`dì` = mother's. Southern and
Central usage differs; regional variants are out of scope and would be a second table, not
edits to this one.

## Giapha query budgets (Phase 10)

Query ceilings are enforced per test; numbers are **measured from the snapshot**, not
guessed. Each ceiling is asserted **against two fixtures: one ~10 person clan and one ~1,000
person clan** — the property tested is that these queries do NOT grow with clan size.

| Endpoint | Actual | Status |
|---|---|---|
| `GET /clans` (list) | 2 | ✓ meets target |
| `GET /clans/{id}/tree` | 3 | ✓ meets target |
| `GET /clans/{id}/persons` (list, paginated) | 3 | ✓ meets target |
| `GET /clans/{id}/persons/{pid}` (detail) | 2 | ✓ beats target (planned 3) |
| `GET /clans/{id}/lich-gio` | 2 | ✓ meets target |
| `GET /clans/{id}/xung-ho` | 3 | **Exceeds target** — plan asked for 2; actual is 2 base + 1 lazy load for non-blood links, or 4 when subject is an in-law (`a` omitted + no common ancestor). The extra query is a `clan_spouse_pairs` lookup needed only when kinship is affinal. Each query is independent of clan size. |
| `GET /public/{slug}/tree` | 4 | **Exceeds target** — plan asked for 3; actual is clan lookup + liveness scan + one requery per non-empty liveness branch, so a mixed clan (both living and deceased) costs 4. Does not grow with clan size. |

**Command budget** (`remind_death_anniversary`): 1 query per clan with nothing due (after
early exit); ~5 per clan with a due giỗ. Test pins `1 + 3` for three quiet clans.

## Test suites

**Total: 579 tests, 4 skipped** (50 `apis/` + 529 `giapha/`). The 4 skips are the tree
benchmarks, which need `BENCHMARK_TREE_PERFORMANCE=1`.

### apis/tests/
- `test_api_snapshots.py` -- freezes the **shape** (keys and types) of all 11 routes.
- `test_api_values.py` -- freezes **exact values** for deterministic endpoints.
  Golden files recorded from pre-refactor code, proving restructuring is behaviour-neutral.
- `test_query_counts.py` -- per-endpoint query ceiling; catches reintroduced N+1.
- `test_services.py` -- unit tests for `services/` (no database).
- `test_security.py` -- ownership and data-exposure regressions.
- `test_file_upload_api.py` -- the presigned file endpoints; `boto3` fully mocked,
  never touches the network. Clears the throttle cache per test because both
  endpoints are unauthenticated and bucket by IP.
- `test_management_commands.py` -- `remind_appointment_date` (the `apis/` reminder;
  unrelated to `giapha/`'s `remind_death_anniversary`).

### giapha/tests/
- Query budgets asserted; 3-query `/tree` contract is verified per-test with `assertNumQueries`.
- Graph tests validate cycle rejection, soft-delete filtering, generation recomputation.
- Permission and invite tests validate 404 (not 403), expiry, role-grant patterns.
- Revision snapshot and restore tests with tree re-validation.
- `test_gio_follow_service.py` runs on `SimpleTestCase` (edge tuples, no database).
- Kinship (phase 7), 109 tests over three files: `test_kinship.py` (82, `SimpleTestCase`,
  the tables and the walks cell by cell), `test_kinship_api.py` (18, HTTP + the query
  budget asserted next to the answer produced), and `test_kinship_reciprocity.py` (9) —
  a property sweep over every pair in a purpose-built clan: if A calls B *X* then B must
  call A the documented counterpart of *X*. Its `RECIPROCAL` / `BY_HAND` /
  `HEDGE_RECIPROCAL` tables are **hand-written and not derived from `TERMS`**; that is the
  entire point, since a table checked against itself checks nothing. It also asserts every
  entry in `TERMS` is reached by some pair, so a new row nobody can reach is caught.
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
- **`apis/views/good_day.py`'s `DateGoodByWorkAPIView`** queries `HiepKy.objects.filter(...)`
  with no `.order_by()`, then sorts Python-side by `percent` only. Rows tied on `percent`
  come back in MySQL's natural order. This causes `apis.tests.test_api_values.test_date_good_by_work_values`
  to fail in isolation but pass in suite (test ordering matters). Pre-existing; unrelated to
  giapha; not fixed as part of this phase.
- **Django 3.1 is end-of-life.** The Dockerfile is pinned to Python 3.9 because
  3.1 does not run on 3.12+. An upgrade path is the next structural piece of work.
