---
phase: 2
title: "De xuat thay doi va duyet"
status: completed
priority: P1
effort: "2d"
dependencies: [1]
---

# Phase 2: Đề xuất thay đổi và duyệt

## Overview
Thành viên sửa được ngoài phạm vi gia đình bằng cách gửi đề xuất. Editor duyệt → áp qua đúng đường ghi hiện có, có lịch sử.

## Requirements
- Functional:
  - Model `ChangeRequest`: `clan`, `proposer` (User, SET_NULL), `target_person` (nullable), `action` ∈ {`create_person`, `update_person`, `delete_person`, `create_marriage`, `update_marriage`, `delete_marriage`}, `target_marriage` (nullable), `payload_json` (TextField — MySQL 5.7), `proposer_note` (nguồn/lý do, max 500), `base_updated_at` (staleness; phase 5 đổi sang `base_version`), `status` ∈ {pending, approved, rejected, expired, withdrawn, stale}, `reviewer`, `review_note`, `created_at`, `reviewed_at`. Index `(clan, status)`.
  - Payload validate **lúc tạo** bằng chính serializer ghi (`PersonWriteSerializer` partial / marriage serializer) → rác không vào hàng đợi.
  - Endpoints:
    - `POST /clans/{id}/change-requests` (member)
    - `GET /clans/{id}/change-requests?status=&mine=1` (editor+: tất cả, `mine=1` lọc của mình; member: luôn chỉ của mình)
    - `GET /clans/{id}/change-requests/{cr_id}` — kèm `current` (giá trị hiện tại) để UI hiện diff
    - `POST .../{cr_id}/approve` `{note?, override_stale?}` (editor+)
    - `POST .../{cr_id}/reject` `{note}` (editor+)
    - `DELETE .../{cr_id}` (proposer, chỉ khi pending → withdrawn)
  - Duyệt: target đổi sau `base_updated_at` → 409 `stale` trừ khi `override_stale=true`. Áp qua service chung, `PersonRevision.actor = reviewer`, snapshot ghi kèm `change_request_id`.
  - Giới hạn 20 pending / proposer / họ.
  - **Hết hạn 30 ngày** (chốt): ngày 7 còn pending → push nhắc người duyệt (1 lần); ngày 30 → `expired` + push người gửi (gửi lại được). Chạy trong management command hằng ngày `expire_change_requests` (cùng lịch cron nhắc giỗ), idempotent.
  - Push FCM: tạo → editor của họ; quyết định → proposer. Best-effort, lỗi không làm hỏng request.
- Non-functional: approve atomic (`transaction.atomic` + `select_for_update` trên CR).

## Architecture
- Tách logic ghi khỏi view: `services/person_write.py` (`apply_person_update`, `apply_person_create`, `apply_person_delete`) + `services/marriage_write.py`. View cũ và approve cùng gọi → một đường ghi (DRY).
- `services/change_request_apply.py`: dispatch theo `action`.
- `services/change_request_notify.py`: gom device token editor → `fcm.send_multicast`.

## Related Code Files
- Create: `giapha/models/change_request.py`, `giapha/migrations/0011_change_request.py`, `giapha/services/person_write.py`, `giapha/services/marriage_write.py`, `giapha/services/change_request_apply.py`, `giapha/services/change_request_notify.py`, `giapha/selectors/change_request.py`, `giapha/serializers/change_request.py`, `giapha/views/change_request.py`, `giapha/views/change_request_review.py`, tests `test_change_request_api.py`, `test_change_request_apply.py`
- Modify: `giapha/models/__init__.py`, `giapha/views/person.py`, `giapha/views/person_list.py`, `giapha/views/marriage.py` (gọi service), `giapha/urls.py`, `giapha/admin/` (thêm `change_request.py`)
- Docs: `docs/api-reference.md`, `docs/gia-pha-architecture.md`

## Implementation Steps
1. Refactor view ghi → `person_write` / `marriage_write`; test cũ phải pass nguyên (bước an toàn, commit riêng).
2. Model + migration + admin.
3. Create/list/detail/withdraw + validate payload lúc tạo.
4. Approve/reject + stale check + revision.
5. Notify + command `expire_change_requests` (nhắc ngày 7, hết hạn ngày 30) + test với FCM mock (pattern trong `test_gio_remind*`).
6. Docs, full suite.

## Success Criteria
- [x] Viewer đề xuất sửa ngày giỗ cụ → editor duyệt → Person đổi + có revision actor = editor.
- [x] Payload sai (ngày mất 13/13) → 400 lúc tạo, không lưu CR.
- [x] Target bị sửa sau khi đề xuất → approve trả 409 stale.
- [x] Người ngoài họ không thấy/không tạo được CR (404).

## Risk Assessment
- Refactor đường ghi có thể đổi hành vi → làm bước 1 trước, không đổi test.
- `delete_person` qua đề xuất phải giữ luật "fail nếu có con tham chiếu".
- Push spam khi họ đông editor → chỉ gửi editor (phase 6: editor có phạm vi chứa target).

## Deviations
- `services/person_write.py`, `services/marriage_write.py`, `services/change_request_apply.py` implemented as `selectors/*` (same ORM-free reason as Phase 1). Change Request list defaults to status=pending and capped at 200 items. Reject now requires a note field.
