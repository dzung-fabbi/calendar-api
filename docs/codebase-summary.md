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

## Query cost, before and after the refactor

| Endpoint | Before | After |
|---|---|---|
| `calendar` (30 days) | 90 | 2 |
| `get-date-good-by-work` | 121 | 3 |
| `than-sat` | 55 | 15 |
| `home` | 29 | 19 |

## Test suites

**Total: 261 tests** (50 `apis/` + 211 `giapha/`).

### apis/tests/
- `test_api_snapshots.py` -- freezes the **shape** (keys and types) of all 11 routes.
- `test_api_values.py` -- freezes **exact values** for deterministic endpoints.
  Golden files recorded from pre-refactor code, proving restructuring is behaviour-neutral.
- `test_query_counts.py` -- per-endpoint query ceiling; catches reintroduced N+1.
- `test_services.py` -- unit tests for `services/` (no database).
- `test_security.py` -- ownership and data-exposure regressions.
- `test_management_commands.py` -- reminder command.

### giapha/tests/
- Query budgets asserted; 3-query `/tree` contract is verified per-test with `assertNumQueries`.
- Graph tests validate cycle rejection, soft-delete filtering, generation recomputation.
- Permission and invite tests validate 404 (not 403), expiry, role-grant patterns.
- Revision snapshot and restore tests with tree re-validation.

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
