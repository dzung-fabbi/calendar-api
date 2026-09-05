# Phase 5 Giapha Documentation Update

**Files updated:** 3  
**New lines added:** 68  
**Total docs size:** 284 LOC (all files well under 800 LOC limit)  
**Status:** Complete

## Changes Made

### 1. system-architecture.md (+57 lines)
Added comprehensive "Dual Lunar Calendar Implementation" section documenting:
- Why two separate lunar implementations exist (Chinese in `apis/`, Vietnamese in `giapha/`)
- Historical Tết divergences (1968, 1969, 1985, 2007) with critical 1985 example
- Package boundary enforcement (no cross-app imports)
- Deliberate code duplication rationale (`can_chi.py` copied, not imported)
- `vn_lunar.py` verification: 0 mismatches vs Hồ Ngọc Đức's original, cross-checked against `lunarcalendar`
- Known limitation: timezone fixed to UTC+7, does not match 1943-45/1947-55/1960-67 historical windows (~230 affected dates)
- Mitigation: `lich-gio` endpoint never enters affected windows; future features need `tz_for_date()` table

**Key passage:** "Using the Chinese calendar for a giỗ would place the anniversary on the wrong day — the core reason the `giapha` module exists."

### 2. codebase-summary.md (+27 lines)
**Added giỗ endpoint to giapha routes table:**
- Route: `GET /api/gia-pha/clans/{clan_id}/lich-gio`
- Permission: `IsClanMember`
- Query contract: exactly 2 (cached role check + single selector query)
- Window: next 12 months (default), configurable via `from`/`to` or `year` params
- Max window: 731 days (2 calendar years)
- Response: `{items: [...], truncated: bool}` with lunar/solar dates, can-chi, days_until, adjusted flag

**Added "Giapha services (Phase 5)" section:**
- `services/vn_lunar.py` — Vietnamese lunar, UTC+7, 1800–2199, no external dep
- `services/gio.py` — giỗ rules (day-30→29 fallback, single-month observation, two per solar year)
- `services/can_chi.py` — deliberate 10-line copy enforcing boundary
- `selectors/gio.py` — single query optimization

**Updated test count:** 261 → 356 tests (added 95 giapha tests for Phase 5)

### 3. code-standards.md (+4 lines)
Enhanced "Decoupling" subsection:
- Clarified deliberate code duplication with concrete example
- Cross-referenced dual-calendar rationale in system-architecture.md
- Emphasized boundary as prerequisite for independent evolution

## Architectural Record

**CRITICAL POINT — Documented to prevent future engineers from "DRY-ing up" the calendars:**

The project deliberately runs two separate lunar calendar implementations. Vietnam and China use different calendars. Unifying them would break the giỗ (death anniversary) calculation on ~230 historical dates and future dates where the intercalary month diverges. 1985 is the most dramatic example: Vietnam's Tết on 21/01, China's on 20/02 (full month difference).

This is not an oversight or technical debt. It is an architectural requirement. The documentation now makes this unambiguous.

## Verification

- All files remain under 800 LOC limit
- Existing section structure preserved (no restructuring)
- Cross-references consistent (system-architecture ↔ code-standards)
- Endpoint documentation matches `views/gio.py` contract
- Test count updated to reflect 356 tests
- No changelog created (per instructions)

## Unresolved Questions

None. All Phase 5 deliverables documented.
