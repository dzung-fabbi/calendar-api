---
phase: 1
title: "Pham vi quyen gia dinh va xac minh"
status: completed
priority: P1
effort: "3d"
dependencies: []
---

# Phase 1: Phạm vi quyền gia đình và xác minh

## Overview
Thành viên thường (viewer) đã được xác minh "tôi là X" tự sửa/thêm được gia đình mình. Tự nhận binding không còn đem lại quyền. Lời mời có thể gắn sẵn một người trong cây. Con cháu (member đã xác minh) tự mời được người trong gia đình mình; mời vượt cấp gia đình cần trưởng họ (owner) hoặc **Ban quản lý** (role mới `manager`) duyệt.

## Requirements
- Functional:
  - Phạm vi gia đình của người P = {P} ∪ vợ/chồng(P) ∪ cha, mẹ(P) ∪ hậu duệ(P) ∪ vợ/chồng của hậu duệ ∪ **anh chị em ruột chưa được nhận** (chốt 2026-09-19).
  - Anh chị em (chung ≥ 1 cha/mẹ) vào phạm vi **chỉ khi** node đó chưa có `ClanMember` với `person_verified=True`. Khi họ đã vào app và được xác minh, chỉ họ (và người duyệt) sửa node của họ. Không lan sang vợ/chồng hay con của anh chị em.
  - Viewer có binding `person_verified=True` được PATCH/DELETE/upload ảnh người trong phạm vi; POST người mới khi cha hoặc mẹ của người mới nằm trong phạm vi; POST/PATCH/DELETE marriage khi ≥ 1 bên trong phạm vi.
  - Owner/editor: như cũ. `force=true` vẫn chỉ owner. Revisions/restore vẫn editor+.
  - UI cần biết quyền để chọn nút và vẽ viền:
    - `GET /clans/{id}/persons/{pid}` thêm `can_edit: 'direct' | 'propose'`.
    - `GET /clans/{id}/tree` thêm `my_editable_ids: [id]` (null khi toàn họ) — tính từ cùng `writable_ids`, không thêm query.
    - PATCH ngoài phạm vi → 403, message gợi ý gửi đề xuất (server **không** tự tạo đề xuất ở `/clans`; chỉ phase 5 làm việc đó cho sửa từ cây cá nhân).
  - `PUT toi-la` do viewer → `person_verified=False`; do editor/owner → `True`.
  - `POST /clans/{id}/members/{user_id}/verify`: xác minh binding; `DELETE` cùng path: từ chối (gỡ binding). **Ai xác minh** (chốt): owner + manager; phase 6 thêm trưởng chi có chi chứa node. Editor thường **không** xác minh.
  - Binding tự nhận chờ xác minh → push cho owner + manager (phase 6: + trưởng chi liên quan).
  - `POST /clans/{id}/invites` nhận `person_id?`, `request_note?`: người phải thuộc họ, chưa bị nhận, chưa mất.
  - **Role mới `manager` — "Ban quản lý"** (phó trưởng họ, duyệt thay khi trưởng họ vắng):
    - `CLAN_ROLE` thêm `('manager', 'Ban quản lý')`; thứ bậc owner > manager > editor > viewer. `INVITE_ROLE` **không** đổi (lời mời không bao giờ cấp manager).
    - Quyền: như editor **toàn họ** (không có phạm vi chi) + duyệt/từ chối lời mời role viewer + xác minh binding + duyệt đề xuất (phase 2) + tạo lời mời active cho bất kỳ người nào trong họ (role viewer).
    - Không được: đổi role, xoá thành viên, sửa/xoá họ, bật link công khai, `force=true`, duyệt/tạo lời mời role editor (chỉ owner).
    - Chỉ owner gán/gỡ manager qua `PATCH /clans/{id}/members/{user_id}` `{role: 'manager'}`.
    - `permissions.py`: `EDITOR_ROLES = ('owner', 'manager', 'editor')`, thêm `APPROVER_ROLES = ('owner', 'manager')` + `IsClanApprover`. Role chỉ được so sánh qua các hằng này (hiện đã tập trung ở `permissions.py`, giữ nguyên kỷ luật đó).
  - **Ai tạo lời mời**: owner (như cũ) + manager + editor + viewer có binding verified (mới). Viewer chưa verified → 403. Quy tắc trạng thái:
    - `active` ngay khi: caller là owner; caller là manager và `role='viewer'`; **hoặc** `role='viewer'` **và** `person_id` nằm trong phạm vi ghi của caller (phạm vi gia đình; editor toàn họ: cả họ; trưởng chi phase 6: cả chi).
    - `pending_approval` khi: người ngoài phạm vi, không gắn người, hoặc `role='editor'` (member không tự cấp editor).
    - Lời mời gắn người: `max_uses=1` bắt buộc.
  - `pending_approval` **không có mã** (`code` NULL) → không lộ link trước khi duyệt; mã sinh lúc duyệt.
  - `POST /clans/{id}/invites/{invite_id}/approve` và `/reject` `{note?}`: **owner hoặc manager** (`IsClanApprover`); lời mời role editor chỉ owner. Duyệt → sinh mã, `status=active`, `approved_by`; push FCM cho người mời. Từ chối → `status=rejected`, push kèm lý do. Lời mời mới cần duyệt → push cho owner + mọi manager.
  - `GET /clans/{id}/invites`: owner/manager thấy tất cả (lọc `?status=pending_approval`); member thấy lời mời của mình. `DELETE`: người tạo hoặc owner.
  - Chống spam: member tối đa 10 lời mời đang active/pending mỗi họ; throttle tạo 20/ngày/user. `/join` với invite có person → tạo member + bind + verified trong cùng transaction; person đã bị nhận lúc redeem → join vẫn thành công, không bind, trả `binding: null` + message.
- Non-functional: kiểm quyền ≤ 2 query thêm/request (edges + marriages, cache trên request như `_giapha_role_cache`).

## Architecture
```
request ─► IsClanMember ─► view gọi can_write_persons(request, clan_id, ids)
                               ├─ role owner/editor → True
                               └─ viewer + binding verified → ids ⊆ family_scope_ids(...)
```
- `services/family_scope.py` (thuần): `family_scope_ids(parent_edges, marriage_pairs, person_id, verified_person_ids) -> set[int]` (tham số cuối để loại anh chị em đã được nhận; lấy bằng 1 query binding verified của họ, cache cùng edges). Hậu duệ = BFS trên `_children_of` (tái dùng `services/tree.py`).
- `permissions_scope.py`: `can_write_persons(...)`, `require_write(...)` raise `PermissionDenied('Bạn chỉ sửa được người trong gia đình mình. Hãy gửi đề xuất.')`. Cache edges trên `request._giapha_scope_cache[clan_id]`.
- Data migration: binding hiện có của owner/editor → verified; viewer → False (thận trọng).
- `services/invite_policy.py` (thuần): `invite_initial_status(role_of_caller, invite_role, person_id, writable_ids) -> 'active' | 'pending_approval'`. Test bảng quyết định đủ tổ hợp.
- Invite gốc (không gắn người) đang có vẫn `active` sau migration.

## Related Code Files
- Create: `giapha/services/family_scope.py`, `giapha/permissions_scope.py`, `giapha/views/member_verify.py`, `giapha/views/invite_review.py`, `giapha/services/invite_policy.py`, `giapha/services/invite_notify.py`, `giapha/migrations/0010_member_verified_invite_person.py`, `giapha/tests/test_invite_policy.py`, `giapha/tests/test_member_invite_approval.py`, `giapha/tests/test_family_scope.py`, `giapha/tests/test_family_scope_permissions.py`, `giapha/tests/test_invite_person_binding.py`
- Modify: `giapha/models/choices.py` (`manager`), `giapha/permissions.py` (`EDITOR_ROLES`, `APPROVER_ROLES`, `IsClanApprover`), `giapha/models/clan.py` (`ClanMember.person_verified`; `ClanInvite.person` FK SET_NULL, `status` active|pending_approval|rejected, `approved_by`, `request_note`, `review_note`, `code` → nullable unique), `giapha/views/person.py`, `giapha/views/person_list.py`, `giapha/views/marriage.py`, `giapha/views/photo.py` (đổi `IsClanEditor` → `IsClanMember` + `require_write`), `giapha/views/member_binding.py`, `giapha/views/clan_membership.py` (invite create + join), `giapha/serializers/clan.py`, `giapha/serializers/gio_follow.py` (expose `person_verified`), `giapha/serializers/person.py` (`can_edit`), `giapha/views/tree.py` (`my_editable_ids`), `giapha/urls.py`
- Docs: `docs/api-reference.md` (bảng quyền mới), `docs/gia-pha-architecture.md`

## Implementation Steps
1. Role `manager` (choices + hằng quyền + PATCH members chỉ owner gán) + model + migration 0010 (schema + data migration verified theo role).
2. `family_scope_ids` thuần + unit test (đa thê, con nuôi, người xoá mềm bị loại, chu trình không có).
3. `permissions_scope.py` với cache; test ma trận role × trong/ngoài phạm vi × verified/không.
4. Đổi 4 view ghi sang `require_write`; POST person: lấy `father_id`/`mother_id` từ payload (bulk: mọi item phải hợp lệ, lỗi → 403 cả lô).
5. `toi-la` PUT set verified theo role; endpoint verify/reject.
6. Invite `person_id` (validate) + join bind trong `transaction.atomic`, `select_for_update` person-claim check.
7. Member tạo lời mời: `invite_policy` + code NULL khi pending; approve/reject (owner) sinh mã + push; list/delete theo người tạo; giới hạn + throttle. `/join` từ chối invite không `active`.
8. Cập nhật docs; chạy full test suite.

## Success Criteria
- [x] Viewer verified sửa con mình → 200; sửa ông nội anh họ → 403 với message gợi ý đề xuất.
- [x] Em ruột chưa vào app → anh sửa được; em đã vào app và được xác minh → anh sửa bị 403 (gửi đề xuất).
- [x] Editor thường gọi verify → 403; owner/manager → 200.
- [x] Viewer tự nhận binding → không sửa được gì tới khi editor verify.
- [x] Join qua invite gắn người → bind + verified; hai người redeem cùng node → chỉ một bind.
- [x] Member verified mời vợ/con mình → `active`, có mã ngay; mời chú (ngoài phạm vi) → `pending_approval`, không mã; owner duyệt → có mã, người mời nhận push.
- [x] Member chưa xác minh tạo lời mời → 403; member tạo invite role editor → luôn pending.
- [x] Editor thường không duyệt được lời mời; manager duyệt được lời mời role viewer, không duyệt được lời mời role editor.
- [x] Manager không đổi được role, không xoá được thành viên, không bật link công khai (403).
- [x] Chỉ owner gán được manager; invite không bao giờ cấp manager (kể cả ghi qua admin: kiểm lại lúc redeem như hiện nay).
- [x] Test hiện có (`test_permissions.py`, `test_person_api.py`) vẫn pass.

## Risk Assessment
- Mở quyền ghi cho viewer = bề mặt tấn công mới → mọi view ghi phải đi qua `require_write`; thêm test "viewer chưa verify" cho từng endpoint ghi.
- Mở quyền tạo lời mời cho member → lời mời không gắn người là cửa cho người lạ: luôn qua owner duyệt; mã chỉ tồn tại khi active.
- Owner vắng mặt → Ban quản lý (manager) duyệt thay; không có manager thì hiện số chờ duyệt + push nhắc owner.
- Thêm role giữa owner và editor: mọi chỗ so role phải qua `EDITOR_ROLES` / `APPROVER_ROLES`; test ma trận quyền thêm cột manager cho **mọi** endpoint.
- POST bulk 200 người trong phạm vi → vẫn giới hạn `MAX_CLAN_PERSONS`.
- Data migration hạ quyền viewer đang bind → không mất quyền nào (trước đây viewer không ghi được).

## Deviations
- Write-path modules live in `giapha/selectors/` not `services/` (services kept ORM-free per docs/code-standards.md). Invite "active immediately" narrowed after security review to **DOWNWARD persons only** (descendants + their spouses); inviting own parent/sibling becomes pending_approval. Marriage by a scoped member: both partners must be in scope, or the other partner must be unattached (no parents, no marriage). Changing father/mother requires the new parent in scope. Invites minted by a member are deleted when that member is removed.
