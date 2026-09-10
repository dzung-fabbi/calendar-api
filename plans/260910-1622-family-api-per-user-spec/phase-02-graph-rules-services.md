# Phase 2 — Pure services (no ORM)

**Priority:** P0 · **Status:** ✅ Done

## Files
- `giapha/services/family_issue.py`: `FamilyRuleError(code, message, person_id, other_id, status)` + bảng message vi.
- `giapha/services/family_graph.py`: `FamilyGraph` dựng từ rows (persons dict + spouse pairs):
  `children_of`, `ancestors`, `descendants` (reuse `person_rules.descendants`), `partners`
  (spouses + co-parents), `slot_for_gender`, `gender_fits_slot`, `is_lineal`.
- `giapha/services/family_rules.py`: `check_set_parent`, `check_link_spouse` (trả warning),
  `check_link_child`, `check_add_relative`, `other_parent_candidates`, `pick_other_parent`.
- `giapha/services/family_labels.py`: bảng nhãn mục 4.8 → plan cạnh `(kind, target)` hoặc hint.
- `giapha/services/family_dates.py`: parse/format `DD-MM-YYYY`, `HH:mm`, epoch ms, `derive_solar_death`.

## Luật (spec §4)
- SELF_PARENT, PARENT_CYCLE, PARENT_SLOT_TAKEN, DANGLING_*, SELF_SPOUSE chặn (400).
- SPOUSE_IS_ANCESTOR chỉ warning. GENDER_MISMATCH (thêm, BE lọc như UI). NO_PARENT_FOR_SIBLING (thêm).
- linkSpouse điền ô cha/mẹ trống của con **chỉ khi vợ/chồng đầu tiên** của người đó.
