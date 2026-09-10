# Personal Family Tree API Documentation Update

**Date:** 2026-09-10  
**Scope:** Document new 13-endpoint `/api/gia-pha/v1/family/` surface (personal family tree, one user = one tree)

## Changes Made

### 1. README.md
- Updated API reference line to mention "13 personal family tree endpoints (`/api/gia-pha/v1/family/`)" alongside existing 26 clan endpoints.

### 2. docs/api-reference.md (Vietnamese)

**Intro table (line 5-9):**
- Added new row: "Gia phả cá nhân (13 endpoint)" → `/api/gia-pha/v1/family/`
- Renamed clan row from "Gia phả (26 endpoint)" → "Gia phả cộng tộc (26 endpoint)" for clarity

**"Bao Đóng Response" section (line 49-59):**
- Clarified that "bốn endpoint gia phả" refers to clan endpoints
- Added note: "Mười ba endpoint gia phả cá nhân (`/v1/family/*`) trả payload phẳng, không bao"

**New major section "## Gia Phả Cá Nhân (`/api/gia-pha/v1/family/`)" (pre-"Response Lỗi"):**
- **Purpose & contract:** Link to specs, single-family per user model
- **13 endpoints table:** Method, path, chức năng, body structure
- **Person JSON structure:** All fields documented (camelCase, date/time format, epoch ms timestamps)
- **Response shapes:** Success (read, mutation, delete envelopes), error envelope with code table
- **Error codes:** SELF_PARENT, PARENT_CYCLE, PARENT_SLOT_TAKEN, etc. — 11 codes + HTTP status
- **3 practical examples:** Add sibling, link spouse with auto-fill, error cases

### 3. docs/system-architecture.md (English)

**Directory structure (`giapha/`):**
- Added models: `family.py` (Family, FamilyPerson, FamilySpouse — separate from clan)
- Added selectors: `family.py`, `family_write.py` (personal tree queries)
- Added services: `family_issue.py`, `family_rules.py`, `family_labels.py`, `family_dates.py`, `family_draft.py`, `family_graph.py`
- Added views: `family_base.py`, `family.py`, `family_relations.py`, `family_link_flow.py`
- Added serializers: `family_output.py`, `family_draft.py`, `family_relations.py`
- Added tests: `test_family_api.py`, `test_family_relations_api.py`, `test_family_rules.py`, `test_family_query_counts.py`

**New subsection "Personal family tree (`/v1/family`)":**
- Design rationale (separate model set, hard delete vs soft delete, explicit deceased flag, ungendered spouses, UUID ids)
- In-memory analysis approach (FamilyGraph per request, 2-query contract)
- Layering explanation (services/selectors/views/serializers separation)
- Payload shape (flat, success/error envelopes)

### 4. docs/codebase-summary.md (English)

**Intro section (line 44-48):**
- Split giapha into "26 clan endpoints" vs "13 personal family tree endpoints (`/v1/family/`)"

**New subsection after kinship calculator:**
- 10-row endpoint table (route, method, view, auth, queries)
- Bullet notes: auth scope, response shape, query budget, models, graph analysis, rules

## Verified Against Code

- ✓ 13 endpoints in `giapha/urls.py` (lines 45-58)
- ✓ Person JSON fields match `serializers/family_output.py` PERSON_KEYS
- ✓ Error codes match `services/family_issue.py` MESSAGES dict
- ✓ Success/error envelope structure verified in `views/family_base.py`
- ✓ Models verified in `models/family.py` (Family, FamilyPerson, FamilySpouse)
- ✓ Query budget (2 per endpoint) verified in `selectors/family.py`

## Documentation Size Check

| File | Before | After | Status |
|------|--------|-------|--------|
| api-reference.md | 613 | 857 | Added ~244 lines (under 1000 limit) |
| system-architecture.md | 555 | 618 | Added ~63 lines (under 1000 limit) |
| codebase-summary.md | 312 | 362 | Added ~50 lines (under 1000 limit) |
| README.md | 15 | 15 | 1-liner update |

All files remain under the maxLoc guideline.

## Notes

- Personal family tree API is fully implemented and deployed; documentation reflects actual code.
- Spec documents (`docs/gia-pha-api-spec.md`, `docs/gia-pha-architecture.md`) are referenced but not edited (mobile app contract).
- All Vietnamese text in api-reference.md; English in system-architecture.md and codebase-summary.md (consistent with existing docs).
- Error handling and mutation semantics (auto-fill, relationship label linking, cycle detection) all documented with practical examples.

## No Unresolved Questions

Documentation is complete and verified against implementation.
