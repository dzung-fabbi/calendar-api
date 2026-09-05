# System Architecture

Django 3.1 + Django REST Framework service with two independent apps. **`apis/`** serves
Vietnamese almanac data (hiệp kỷ, thần sát, tiết khí, sao, tử vi số học). **`giapha/`**
serves Vietnamese family-tree (gia phả) records. MySQL 5.7 storage; OAuth2 / social auth
for authenticated endpoints.

## Layers

Both apps follow identical layering:

```
apis/ | giapha/
├── models/      ORM only. No behaviour beyond field definitions.
├── selectors/   Bulk read helpers. Everything that batches or prefetches.
├── services/    Calculation. No ORM, no request. Unit-testable in isolation.
├── serializers/ Response shaping.
├── views/       HTTP: validate params -> selectors/services -> serializers.
├── admin/       Django admin, inlines built by factory.
├── management/  Batch jobs (cron entry points). May hold ORM writes services cannot.
└── tests/       Snapshot, value, query-count, service, security suites.
```

The dependency direction is one-way: `views -> serializers/selectors/services -> models`.
`services/` imports nothing from Django's ORM, which is what lets it be tested
with `SimpleTestCase` (no database).

**The rule is "no ORM", not "no I/O".** `giapha/services/fcm.py` performs HTTP and still
belongs there; what it may not do is write a model. See "Push Notification Channel".

**Decoupling rule:** `giapha/` and `apis/` share no imports; code is duplicated if needed.
This is enforced to allow independent evolution.

## Data model shape (apis/)

The schema is unusually wide: the twelve hours of a day and the twelve months
of a thần sát year each get their own through-table (`SaoHour1..12`,
`SaoMonth1..12`) rather than one table with an `hour` / `month` column. That is
the single largest remaining performance constraint -- see
`docs/codebase-summary.md`.

Column definitions for the twelve monthly tables live on one abstract base
(`SaoMonthBase`); Django names each concrete table after its own class, so this
is a source-level change with no schema effect.

## Giapha Design Decisions

**Python tree traversal, not SQL recursion.** MySQL 5.7 has no `WITH RECURSIVE`.
The entire clan (up to 5000 persons) loads in one `selectors/` query and is
walked in Python. Closure table / materialized path were rejected as over-engineering
at this scale; the limit lives in `settings.MAX_CLAN_PERSONS` and would need to
change first before SQL recursion became cost-justified.

**`GET /tree` is a hard 3-query contract**, asserted per-test by `assertNumQueries`.
One query checks permission; one fetches all `Person` rows; one fetches all `Marriage`
rows. Parent edges are derived from already-fetched rows. Nodes are intentionally lean
(no `tieu_su`, `que_quan`, details) -- depth comes from `GET /persons/{pid}`.
Layout coordinates are computed client-side.

**`generation` is derived state**, computed by topological walk, persisted on write,
and never client-writable. Subtree recompute on parent change uses `bulk_update`;
whole-clan recompute is a management command, kept out of request paths.

**Cycle safety is defence-in-depth.** Parent-child cycles are rejected at API write time,
but Django admin bypasses serializer validation entirely, so every graph walk must also
survive corrupt data -- bounds fail CLOSED (raise) rather than returning partial results,
because a partial descendant set would let a real cycle pass the API validation gate.
The one deliberate exception is `services.gio_follow.ancestors`, which fails OPEN because
it feeds a background job rather than a write gate -- see "Push Notification Channel".

**Authorization:** three permission classes keyed off `clan_id` in URL; role is cached
on request (≤1 query per check). Non-members receive **404, never 403** -- a 403 would
confirm the clan exists.

**Soft delete** on `Clan.is_deleted` and `Person.is_deleted`; every selector filters
`is_deleted=False` consistently or the tree silently fractures.

**Invites** grant editor/viewer only (never owner -- ownership transfers via member PATCH).
Default 30-day expiry, revocable, and redeemable only once. Redemption locks the row
with `select_for_update` inside `transaction.atomic` and re-checks role, because admin
can write invite rows that bypass the serializer. `/join` is the only throttled endpoint
in the project (`giapha-join` scope: 10/hour).

## Push Notification Channel (Phase 6)

The first outbound channel in this codebase: everything before it was request/response
only. One nightly management command, no Celery — one job a day does not justify a broker.

> **Status: real-device delivery is UNVERIFIED.** No Firebase project has been created,
> and every test mocks the FCM layer (`requests.post`, `_mint_token`, `send_multicast`).
> What is proven is recipient resolution, de-duplication, and failure classification.
> What is not proven is that a handset ever receives a notification.

### Follow resolution: computed, never stored

The set of people a user is reminded about is **resolved at send time**, not materialised.

```
ClanMember.person   "I am this node"        (one row per member, nullable)
        |
        v
services.gio_follow.ancestors(edges, self_person_id)
        |                       ^
        |                       |  selectors.person.clan_edges_all
        |                          (INCLUDES soft-deleted rows)
        v
   default set = direct-line ancestors (father AND mother, no gender filter,
                 no descendants, no collaterals)
        |
        +-- GioFollow(enabled=True)  -> add     (source: thu-cong)
        +-- GioFollow(enabled=False) -> remove  (source: da-bo)
        |
        v
   followers_by_person -> {person_id: {user_id, ...}}
```

Consequences that follow directly from this design:

- Editing `father` / `mother` in the tree changes every affected follow set immediately.
  **There is no re-sync job and none is needed.**
- Three states, not two — hence both `PUT` and `DELETE` on an override. Without `DELETE`
  a user who switched an ancestor off could only get back to a manual "on" that no longer
  tracks the tree.
- **A member with no binding receives nothing by default.** Guessing which node a user is
  would push another family's giỗ at them; silence is the honest answer.
- Traversal uses `clan_edges_all`, so a soft-deleted ancestor does not sever the line
  above them. Nobody is ever notified *about* a soft-deleted person — the candidate set
  comes from `deceased_with_lunar_death`, which filters `is_deleted=False`.
- `overrides_for_clan` joins `ClanMember` as a **privacy guard**: removing a member drops
  their membership row but leaves their `GioFollow` rows standing, and without the join
  an ex-member would keep receiving a deceased person's name from a clan that now answers
  404 to them on every endpoint. The rows survive so rejoining restores preferences.

**Cycle policy inverts here.** `services.gio_follow.ancestors` fails **OPEN** (returns the
partial set) where `services.person_rules.descendants` fails **CLOSED** (raises). Both are
correct: `descendants` gates a write, so a partial answer would let a real cycle through
the validation gate; `ancestors` feeds a nightly batch, where missing a few recipients
beats killing the run.

### Send path

```
cron (Vietnam morning)
  -> manage.py remind_death_anniversary
     -> collect_due(today_vn())        reads + arithmetic only
        per clan: deceased_with_lunar_death  <-- EARLY EXIT if nothing due
                  clan_edges_all / binding_map / overrides_for_clan
                  followers_by_person -> active_tokens_for
        -> [GioJob(..., recipients={user_id: [token]})]
     -> dispatch(jobs)                 the only half that touches the network
        notified_pairs()               one query, status='sent' only
        services.fcm.send_multicast()  HTTP v1, one POST per token, shared bearer
        _gio_reminder_log.deactivate_dead() / log_attempt()   the only ORM writes
```

**Query budget: 1 per clan on a quiet day.** `deceased_with_lunar_death` runs first and
the clan is abandoned before the other four queries whenever nothing is due — which is
almost every clan on almost every day. Reordering that early exit multiplies a nightly
job's cost by five per clan.

**Timezone is load-bearing.** The command computes today with `services.gio.today_vn()`,
never `timezone.localdate()`. `settings.TIME_ZONE` is `'UTC'` with `USE_TZ=True`, so a
cron firing before 07:00 Vietnam time would otherwise compute the *previous* day and send
every reminder one day off.

**Layering holds even with a network.** `services/fcm.py` performs HTTP but touches no
ORM: it *reports* a dead token, and the command deactivates it. That is why
`_gio_reminder_log.py` sits under `management/commands/` rather than in `services/`.

### Failure taxonomy — three outcomes, deliberately distinct

| Condition | Signal | Effect |
|---|---|---|
| No / malformed credentials | `send_multicast` → `{}` | Command warns, exits **0**, no stacktrace. Cron stays quiet. |
| Credentials file unreadable *right now* (rotation, flaky mount) | `FcmTransientError` → `{token: network_error}` | **Retriable**, not "unconfigured". The rest of the batch continues. |
| `UNREGISTERED` / `INVALID_ARGUMENT` from FCM | matched against `DEAD_TOKEN_RESULTS` | `DeviceToken.is_active = False`. |
| 5xx, timeout, DNS | `network_error` | Token stays **active**; `failed` log row; retried on the next run. |

Collapsing "unconfigured" into "transient" once abandoned every remaining recipient of a
run *and* printed "Firebase is not configured" in a run where a push had already gone out.
`{}` from `send_multicast` means "nothing to attempt with" and nothing else.

### De-duplication and retry

`GioNotificationLog`'s `unique_together ('person','user','solar_date')` is the guarantee;
`notified_pairs()` reads it up front so a second run of the same day sends nothing rather
than sending and only then failing to record it.

**Only `sent` rows block.** A `failed` row must not, because a person is due on exactly
one calendar day a year (`target = today + gio_remind_before_days` advances with `today`)
— a pair blocked by a failed attempt would never be retried at all, and a 07:00 DNS blip
would cost that ancestor their giỗ notice for a year.

### Security posture

- Device tokens are credentials: accepted in a body, **never** returned in a response,
  redacted to a 6-char prefix plus length in every log line.
- **Accepted risk, recorded not overlooked:** the `POST /devices` upsert is keyed on
  `token` alone, so whoever presents a token owns it from that moment. Required for the
  shared-handset / re-login case; it also means anyone who learns another user's FCM token
  can redirect that handset's reminders. The read direction stays safe and the write is
  authenticated. Revisit the spec before "fixing" it.
- The service account JSON must never be committed.

## Dual Lunar Calendar Implementation

**Two independent lunar calendar implementations exist and must NOT be unified.**

- **`apis/`** uses `lunarcalendar` (PyPI) — Chinese lunar calendar at UTC+8 timezone.
  Used for almanac endpoints (`home`, `than-sat`, etc.). Golden-snapshot tests depend on it.
- **`giapha/`** uses `services/vn_lunar.py` — Vietnamese lunar calendar at UTC+7 timezone.
  Used for giỗ (death anniversary) calculations.

**Reason:** Vietnam and China use different lunar calendars. Historical Tết divergences:
1968, 1969, 1985, 2007. Most critical: 1985, where the intercalary month placed Vietnam's
Tết on 21/01 and China's on 20/02 (full month apart). Using the Chinese calendar for a giỗ
would place the anniversary on the wrong day — the core reason the `giapha` module exists.

**Package isolation:** `giapha/` shares no imports from `apis/`. Code duplication is
deliberate (e.g., `giapha/services/can_chi.py` copies `apis/services/can_chi.py`).
This boundary is enforced to allow independent evolution.

**`vn_lunar.py` verification:** Differential against Hồ Ngọc Đức's own `amlich.js` over
1800–2199 (both directions): 0 mismatches. Cross-check against `lunarcalendar` at tz=8
over 1950–2050: 0 mismatches. Supported range: 1800–2199. No external dependency.

**Known limitation:** `vn_lunar.TIMEZONE` is fixed to 7. Vietnam used UTC+8 during
1943-01-01..1945-09-14, 1947-04-01..1955-06-30, 1960-01-01..1967-12-31. Converting a
solar date inside those windows disagrees with the calendar in force at the time on ~230
dates. The `lich-gio` endpoint never hits this (sweeps forward from modern windows), so
current code is correct. Any future "enter ancestor's solar death date" feature requires
a `tz_for_date()` lookup table first.

## Request path, `/api/home` as the example

1. `views/params.py` validates and coerces the query string; a bad parameter is
   a 400 that names the parameter.
2. `selectors/stars.py` supplies `Prefetch` objects that join each through-table
   to `sao` (and `sao.category` where the serializer renders it).
3. `serializers/` walk only prefetched relations -- `star_payload()` reads
   `row.sao` and must never be handed an unprefetched queryset.

## Collation dependency

The app relies on MySQL's case-insensitive `utf8_unicode_ci`: `HomeAPIView`
matches one `lunar_day` parameter against `HiepKy.lunar_day` (stored upper-case)
and `QuyNhan.can_ngay` (stored capitalised). The test suite therefore runs
against real MySQL, not SQLite -- see `djangopj/settings_test.py`.

`CalendarAPIView` indexes days in memory with an upper-cased key and falls back
to a database lookup when that misses, so the looser SQL matching is preserved.

## Configuration

All secrets and environment-specific values come from environment variables;
see `.env.example`. `djangopj/settings_test.py` supplies test defaults.
