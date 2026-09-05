---
name: giapha-phase-05-lunar-gio-review
description: Adversarial code review of giapha phase 5 (vn_lunar + lich gio) — algorithm verified byte-exact vs Hồ Ngọc Đức's amlich.js over 146,097 days; 1 critical 500, 2 high scaling gaps, pre-1968 timezone limitation
date: 2026-09-05
phase: 5
plan: 260905-1053-gia-pha-dong-ho
---

# Code Review — giapha Phase 5 (`vn_lunar` + lịch giỗ)

## Scope

`giapha/services/{vn_lunar,gio,can_chi}.py`, `giapha/{selectors,serializers,views}/gio.py`,
3 test modules, urls + `__init__` wiring. ~1200 LOC incl. tests.

## 1. Algorithm correctness — VERIFIED EXACT (plan's highest-risk item, cleared)

Not eyeball-diffed. Fetched Hồ Ngọc Đức's actual JS (`trongthanh/amlich.app` →
`src/lib/amlich.js`, the 2006 HND source with `INT = Math.floor`), ran it under node,
differentialled against the Python:

- **solar→lunar: all 146,097 days of 1800-01-01 … 2199-12-31 → 0 mismatches** (day, month, year, leap flag).
- **lunar→solar: 38,496 vectors** (every `ly` 1799-2199 × `lm` 1-12 × `leap` 0/1 × `ld` ∈ {1,15,29,30}) **→ 0 mismatches.**
  All 18,656 Python `ValueError`s are the deliberate bad-`is_leap` raise where JS returns
  `[0,0,0]` or silently falls back to the regular month.

Confirmed term-by-term: all 13 `c1` correction terms and signs, both `delta_t` branches and
the `t < -11` cutoff, `jd1` coefficients, `sun_longitude` M/L0/DL coefficients, the
`diff = floor((month_start - a11)/29)` → `lunar_month = diff + 11` mapping, the
`diff >= leap_month_diff → diff + 10` leap shift, the `lunar_month >= 11 and diff < 4 →
lunar_year -= 1` boundary correction, and the do-while transliteration in `get_leap_month_offset`.

**`math.floor` audit: clean.** Both places where an operand actually goes negative — `k` for
pre-1900 dates, and `lon` normalisation for `t < 0` (`l0 ≈ -71721°` at 1800) — use floor.
None missing.

**Improvement over the reference:** raising on a bad `is_leap` instead of JS's silent
`[0,0,0]`/regular-month fallback. Correct call for this domain.

## 2. The 1985 question — implementation right, plan artifacts wrong

Independently confirmed: **VN Tết Ất Sửu = 21/01/1985; China = 20/02/1985.** VN placed the
leap month in month 2 of Ất Sửu; China in month 10 of Giáp Tý 1984. Documented VN/CN Tết
divergences since 1967: **1968, 1969, 1985, 2007** — exactly what the module produces at
tz=7 vs tz=8.

Root cause of the error, visible in the artifact itself: the researcher report's
"reference implementation" was run at **tz=8**, i.e. it was reading the Chinese calendar.
Its "corrected using computed vectors from reference implementation" line is a false
confidence signal.

→ Both `plan.md` and the researcher report have since been corrected.

## Findings

### CRITICAL

**C1 — `?year=` outside `datetime.date`'s range → HTTP 500.** `views/gio.py`

`dt.date(year, 1, 1)` ran *before* `_validate_window`:

| param | result |
|---|---|
| `?year=0` / `?year=-1` / `?year=10000` | `ValueError` |
| `?year=99999999999` | **`OverflowError`** |

No `EXCEPTION_HANDLER` override in settings → DRF returns `None` for non-`APIException` →
Django 500 + traceback. Note the `OverflowError`: the obvious `except ValueError` does **not**
catch it. Untested because `OutOfRangeTests` used 1799/2200, both valid `date` years.

**FIXED** — year range-checked against `MIN_YEAR`/`MAX_YEAR` before any `date` construction;
`MalformedYearTests` added covering 0, negative, 10000, bignum.

### HIGH

**H1 — Unbounded response; breaks the cap convention from phase 4.** `selectors/gio.py`

No `MAX_CLAN_PERSONS` bound, no `truncated` flag, while `selectors/tree.py` explicitly bounds
with `[:max_persons + 1]`. At the 5,000 ceiling over a 2-year window: ~10,000 un-paginated items.

**FIXED** — bounded at the DB, returns `(rows, truncated)`, `truncated` surfaced in the response.

**H2 — No memoization of the two expensive pure functions.** `vn_lunar.py`

| workload | before | after |
|---|---|---|
| 5000 persons × 2-year window | **0.82 s** | **0.125 s** |

`get_lunar_month_11` and `get_leap_month_offset` are pure but were recomputed per person per
year; each `get_leap_month_offset` miss costs up to 14 `new_moon()` + `sun_longitude()`
evaluations. Endpoint is unthrottled, making this the cheapest CPU-amplification vector in the
module. `_month_start_jd` also called `get_leap_month_offset` twice per invocation.

**FIXED** — `lru_cache` on both; `_leap_month_number` now returns the offset so it is computed
once. Measured 10,330 cache hits vs 2 misses on a 5,000-person sweep.

### MEDIUM

**M1 — Fixed `TIMEZONE = 7` wrong for pre-1968 Vietnamese dates.**
Vietnam was on UTC+8 for 1943-01-01…1945-09-14, 1947-04-01…1955-06-30, 1960-01-01…1967-12-31.
Measured: **230 days across 8 month-boundary runs** where fixed tz=7 disagrees with the official
VN calendar of the time. E.g. solar 1965-02-01 → module says lunar 1/1/1965 (mùng 1 Tết);
official VN calendar (Tết Ất Tỵ = 02/02/1965) says 30/12/1964 — off by a month *and* year.
Also produces a spurious 1965 divergence not in the documented list.

Latent, not live: `lich-gio` never converts historical solar dates. But phases 6/8 or any
"convert my ancestor's solar death date" feature will hit it — and pre-1968 ancestors are
exactly this app's population.

**DOCUMENTED** — caveat added to `vn_lunar.py`; logged as open question 10 in `plan.md`.
`tz_for_date()` table deferred pending a product call.

**M2 — Module docstring understated the divergence set** (omitted 1969 and 1985, the largest).
**FIXED.**

**M3 — Spec success criterion not implemented: no cross-check against `lunarcalendar`.**
`TimezoneDivergenceTests` compares tz=7 to tz=8 *of the same code* — proves the `+ tz/24` term
is wired, not that the algorithm is right; would pass unchanged if both branches were wrong the
same way. The one place the suite asserted the implementation against itself on load-bearing
behaviour.
**FIXED** — `ChineseCalendarCrossCheckTests` added: matches `lunarcalendar` at tz=8 over
1950–2050 (every 13 days, >2500 dates, 0 mismatches), and asserts VN *differs* from it on the
known divergence dates.

**M4 — Boundary vectors violated the file's own sourcing policy** (no provenance).
Both values are in fact correct — matched the reference JS in the differential.
**FIXED** — tagged `[REF]` citing the differential.

**M5 — Invalid stored lunar data yielded a plausible wrong date instead of being skipped.**
`validate_lunar_death_valid` guards only the API write path; a row from admin/fixture/import
with `death_lunar_month=13` or `death_lunar_day=31` flowed through and produced a well-formed
date in the wrong month — no exception, no flag.
**FIXED** — `gio_occurrence` range-guards day/month and returns `None`;
`InvalidStoredLunarDataTests` added, including that one bad row does not hide the good ones.

### LOW

| # | Finding | Status |
|---|---|---|
| L1 | `death_lunar_leap` fetched but never used | **FIXED** — dropped from the selector with a comment saying why |
| L2 | `MAX_WINDOW_DAYS = 366*2` permitted a 733-day "2 year" window | **FIXED** — 731 |
| L3 | `from`/`to` parsed before the year-conflict check | **FIXED** — checked on raw presence |
| L4 | `today + 365` is one short of 12 months across a leap February | **FIXED** — `_one_year_from()` |
| L5 | Index claim unverified | **SOFTENED** — docstring now says EXPLAIN not run; open question 13 |
| L6 | `?year=1800` reaches `get_lunar_month_11(1798)`, one year below the stated band | Noted; ±1 day at worst |
| L7 | No benchmark test, unlike phase 4's `test_tree_performance_benchmark.py` | Deferred |

## Clean on review

- **Permissions / tenant isolation** — `[IsAuthenticated, IsClanMember]`; outsiders get 404 never 403;
  soft-deleted clan also 404. DRF runs `check_permissions` in `initial()` *before* the handler, so an
  outsider sending `?year=abc` gets 404 not 400 — no existence leak via the error channel. Cross-clan test present.
- **Query budget = 2** — verified by reading, not just `assertNumQueries`: selector materialises with
  `list()`, `_items_for` iterates plain dicts from `.values()`, `can_chi_for_date` is pure, no serializer
  field touches a relation. (Tests use `force_authenticate`; production adds OAuth2 token/user lookups on
  top — same convention as `tree.py`'s "exactly 3".)
- **Giỗ rules vs the 3-rule spec table** — exact match. `lunar_month_length` measuring the gap to the next
  new moon rather than probing day 30 is the right call.
- **Inclusive window bounds**, **`lunar_years_covering` ±1 widening**, **`today_vn()`** avoiding
  `timezone.localdate()` under `TIME_ZONE = UTC` — all correct and tested.
- **Backwards compat** — additive only; `__init__` re-export wiring consistent across all three packages.
- **Tests worth keeping:** `test_two_occurrences_in_one_solar_year` and `test_month_11_can_also_double_up`
  use hardcoded solar dates and catch the single most likely design error in the feature.
  `test_consecutive_days_advance_the_lunar_day_by_one` and the 13k-sample round-trip are real invariants.

## Unresolved questions

1. **Pre-1968 timezone — phase 5 or a phase-6 follow-up?** Real wrong-giỗ path for pre-1968 ancestors,
   currently unreachable from this endpoint. Product call, not engineering.
2. **Should `lich-gio` paginate?** Now bounded + `truncated`, but ~10k items is still a large response.
   Better decided before clients ship.
3. **Should the API pass `death_lunar_leap` through at all?** Stored by phase 3, deliberately ignored by
   phase 5. If nothing will ever read it, phase 3 is storing a dead field.
4. **Does `giapha_person_clan_gio_idx` actually get chosen?** Needs `EXPLAIN` against a realistic table.

---

**Status:** DONE_WITH_CONCERNS (all CRITICAL/HIGH/MEDIUM findings since fixed — see statuses above)
**Summary:** Algorithm verified byte-exact against Hồ Ngọc Đức's own JS across all 146,097 days of
1800–2199 in both directions, 0 mismatches — the plan's highest-risk item is cleared, and the
implementation (not the researcher report or plan.md) was right about Tết 1985.
**Concerns/Blockers:** None outstanding in code. The pre-1968 timezone limitation (M1) is documented
and deferred pending a product decision.
