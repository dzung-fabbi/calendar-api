# Phase 4 — Views + urls

**Priority:** P0 · **Status:** ✅ Done

## Files
- `giapha/views/family_base.py`: `FamilyAPIView` (auth, load family, `respond(...)`, đổi
  `FamilyRuleError`/validation → envelope lỗi).
- `giapha/views/family.py`: GET family, GET/POST/PATCH/DELETE persons, PUT self, PUT gio-event.
- `giapha/views/family_relations.py`: add-relative, set-parent, link-spouse, unlink-spouse, link-child.
- `giapha/views/family_link_flow.py`: luồng chung `link_spouse_with_fill`, `link_child_with_fill`,
  `auto_link_by_label` dùng bởi cả views trên.
- Edit `giapha/views/__init__.py`, `giapha/urls.py`.

## Response
- Thành công: phẳng theo spec §8. Sau mutation trả `persons[]` đầy đủ.
- Lỗi: `{ok:false, error:{code, personId?, otherId?, message}}`; 404 `PERSON_NOT_FOUND`; 400 còn lại;
  validation → `VALIDATION` + `fields`.
