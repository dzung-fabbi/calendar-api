---
phase: 6
title: "Editor theo chi"
status: completed
priority: P3
effort: "1d"
dependencies: [1, 2]
---

# Phase 6: Editor theo chi

## Overview
Họ lớn chia chi: trưởng chi là editor chỉ trên nhánh của mình. Đề xuất được chuyển đúng người duyệt.

## Requirements
- Functional:
  - `ClanMember.scope_root_person` (FK Person, nullable, `on_delete=PROTECT`) — chỉ có nghĩa với role `editor`; owner và manager luôn toàn họ (gán scope cho manager → 400); null = toàn họ.
  - Phạm vi chi = hậu duệ(root) ∪ {root} ∪ vợ/chồng của họ (tái dùng `family_scope` phần hậu duệ).
  - `PATCH /clans/{id}/members/{user_id}` nhận `scope_root_person_id?` (owner). Đổi role khác editor → xoá scope.
  - `can_write_persons`: editor có scope → mọi id phải trong phạm vi chi (hợp với phạm vi gia đình nếu có binding verified).
  - ChangeRequest: list/approve/reject chỉ khi target (hoặc cha/mẹ của người mới) trong phạm vi chi; notify chỉ editor có phạm vi chứa target + editor toàn họ + owner.
  - Verify binding (phase 1): trưởng chi verify được node trong chi mình (bổ sung vào owner + manager); nhận push khi có người tự nhận trong chi.
- Non-functional: không thêm query (dùng lại cache edges phase 1).

## Architecture
- `services/family_scope.py` thêm `branch_scope_ids(edges, marriages, root_id)`.
- `permissions_scope.py` hợp nhất: `writable_ids(member) = branch_or_all ∪ family_scope_if_verified`.

## Related Code Files
- Create: `giapha/migrations/0015_member_scope_root.py`, `giapha/tests/test_branch_editor.py`
- Modify: `giapha/models/clan.py`, `giapha/services/family_scope.py`, `giapha/permissions_scope.py`, `giapha/views/clan_membership.py`, `giapha/serializers/clan.py`, `giapha/selectors/change_request.py`, `giapha/services/change_request_notify.py`, `giapha/views/member_verify.py`
- Docs: `docs/api-reference.md`, `docs/gia-pha-architecture.md`

## Implementation Steps
1. Field + migration; `clean()` kiểm root cùng họ (như `ClanMember.clean`).
2. `branch_scope_ids` + test.
3. Gắn vào `can_write_persons`, CR routing, verify.
4. Member PATCH; docs; full suite.

## Success Criteria
- [x] Trưởng chi 2 sửa được cháu chi 2, không sửa được chi 1 (403).
- [x] Đề xuất sửa người chi 1 không hiện trong hàng đợi trưởng chi 2.
- [x] Owner không bị ảnh hưởng.

## Risk Assessment
- PROTECT chặn admin hard-delete root → message rõ trong admin; soft-delete không ảnh hưởng.
- Scope rỗng do root bị xoá mềm → vẫn tính hậu duệ (xoá mềm không cắt cạnh).

## Deviations
- Branch editors' self-binding auto-verified only inside their branch. Restore requires write scope.
