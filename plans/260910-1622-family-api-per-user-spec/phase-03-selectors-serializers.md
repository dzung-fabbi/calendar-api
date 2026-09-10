# Phase 3 — Selectors + serializers

**Priority:** P0 · **Status:** ✅ Done

## Files
- `giapha/selectors/family.py`: `family_for(user)` get_or_create; `load_rows(family_id)` (2 query);
  `get_person(family, id)`.
- `giapha/selectors/family_write.py`: ORM writes trong transaction — `create_person`, `apply_draft`,
  `set_parent_slot`, `upsert_spouse`, `delete_spouse`, `delete_person` (trả detachedFrom).
- `giapha/serializers/family_draft.py`: `PersonDraftSerializer` camelCase → snake (source=), validate
  name 1–60, gender, dates, giờ, lunar ranges, relationship 24, note 200.
- `giapha/serializers/family_output.py`: `person_to_dict(row, spouses)` camelCase, epoch ms, str uuid.
- `giapha/serializers/family_relations.py`: body serializers cho 5 mutation + self + gio-event.
