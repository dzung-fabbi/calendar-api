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
├── services/    Pure calculation. No ORM, no request. Unit-testable in isolation.
├── serializers/ Response shaping.
├── views/       HTTP: validate params -> selectors/services -> serializers.
├── admin/       Django admin, inlines built by factory.
└── tests/       Snapshot, value, query-count, service, security suites.
```

The dependency direction is one-way: `views -> serializers/selectors/services -> models`.
`services/` imports nothing from Django's ORM, which is what lets it be tested
with `SimpleTestCase` (no database).

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
