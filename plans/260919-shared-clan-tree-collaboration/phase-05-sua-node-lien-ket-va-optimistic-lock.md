---
phase: 5
title: "Sua node lien ket va optimistic lock"
status: completed
priority: P2
effort: "2d"
dependencies: [1, 2, 3, 4]
---

# Phase 5: Sửa node liên kết và optimistic lock

## Overview
Sửa một node đã liên kết trong cây cá nhân: field riêng lưu ở cá nhân, field chung đi vào họ (ghi thẳng nếu có quyền, không thì thành đề xuất). Thêm `version` để hai người sửa cùng lúc không đè nhau.

## Requirements
- Functional:
  - Clan `Person.version` (int, default 1), tăng ở **mọi** đường ghi: PATCH, restore, approve CR, photo confirm/delete, bootstrap không cần.
  - `PATCH /clans/{id}/persons/{pid}` nhận `version?` (body) — có và lệch → 409 `{code: 'VERSION_CONFLICT', current}`; không gửi → như cũ (tương thích ngược).
  - ChangeRequest chuyển `base_updated_at` → `base_version` (migration giữ cột cũ tới khi hết pending cũ, hoặc map pending cũ → stale).
  - `PATCH /v1/family/persons/{id}` khi person có link:
    - Tách draft: field riêng → FamilyPerson; field chung → với **mỗi** link: `can_write_persons` → áp qua `person_write` với `version` client gửi (`clanVersions: {clanId: n}`); không quyền → ChangeRequest.
    - Response thêm `clanWrites: [{clanId, result: 'applied'|'proposed'|'conflict', changeRequestId?, current?}]`.
    - Một họ conflict không chặn ghi field riêng và họ khác.
  - Mutation quan hệ cá nhân (`add-relative`, `set-parent`, ...) **không** lan sang họ.
  - `add-relative` từ node đã link → tuỳ chọn `contributeTo: [clanId]` gọi luồng contribute phase 4 sau khi tạo.
- Non-functional: tăng version bằng `F('version') + 1` trong cùng `update()` để tránh race.

## Architecture
```
PATCH /v1/family/persons/{id}
  ├─ private fields → FamilyPerson.save()
  └─ for link in links(person):
        can_write? ─yes→ person_write.apply_person_update(version) ─409→ conflict
                   └no→ ChangeRequest(update_person, base_version)
```
- `services/family_linked_edit.py` điều phối, gọi field map + person_write + change_request.
- `services/person_version.py`: `check_and_bump(person, expected)`.

## Related Code Files
- Create: `giapha/services/family_linked_edit.py`, `giapha/services/person_version.py`, `giapha/migrations/0014_person_version_cr_base_version.py`, tests `test_person_version.py`, `test_family_linked_edit.py`
- Modify: `giapha/models/person.py`, `giapha/models/change_request.py`, `giapha/services/person_write.py`, `giapha/services/revision.py` (restore bump), `giapha/views/photo.py`, `giapha/views/family.py`, `giapha/serializers/family_draft.py` (`clanVersions`), `giapha/serializers/family_relations.py` (`contributeTo`), `giapha/serializers/person.py` (expose `version`)
- Docs: `docs/api-reference.md`, `docs/gia-pha-api-spec.md`

## Implementation Steps
1. `version` + bump ở mọi đường ghi (grep mọi `.save()` / `update()` trên Person trong `giapha/`); test mỗi đường tăng đúng 1.
2. Version check trên PATCH clan; CR `base_version`.
3. `family_linked_edit` + response `clanWrites`.
4. `contributeTo` trên add-relative.
5. Docs; full suite.

## Success Criteria
- [x] Hai client PATCH cùng version → một 200, một 409.
- [x] Viewer sửa tên cụ (ngoài phạm vi) từ cây cá nhân → note cá nhân lưu ngay, tên thành đề xuất `proposed`.
- [x] Client cũ không gửi `version` vẫn chạy.
- [x] Set-parent cá nhân không đổi gì ở họ.

## Risk Assessment
- Sót một đường ghi không bump → conflict không phát hiện; test grep-based + test từng endpoint.
- Partial success nhiều họ khó hiểu với user → response liệt kê từng họ, UI hiện rõ.

## Deviations
- Optimistic lock implemented via row lock (`selectors/person_version.lock_and_bump`) rather than F()+1 update for cleaner semantics. Approve passes `base_version` as `expected_version` for race fix.
