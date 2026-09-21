---
title: "Gia pha dung chung: quyen gia dinh, de xuat, lien ket ca nhan-ho"
description: "Nhieu nguoi cung xem/sua gia pha dong ho: pham vi quyen gia dinh, de xuat-duyet, lien ket tham chieu cay ca nhan <-> dong ho (khong dong bo)."
status: completed
priority: P2
branch: "master"
tags: [giapha, permissions, collaboration, backend]
blockedBy: []
blocks: []
created: "2026-09-19T03:17:24.991Z"
createdBy: "ck:plan"
source: skill
---

# Gia pha dung chung: quyen gia dinh, de xuat, lien ket ca nhan-ho

## Overview

Cho nhiều người cùng làm việc trên một gia phả dòng họ (`/clans`) mà vẫn giữ gia phả cá nhân (`/v1/family`) riêng tư, đa họ.
Nguồn quyết định: [brainstorm-260919-shared-clan-tree-collaboration.md](../reports/brainstorm-260919-shared-clan-tree-collaboration.md)

## Quyết định đã chốt

| Hạng mục | Quyết định |
|---|---|
| Hai cây | Giữ cả hai. Node cá nhân **liên kết tham chiếu** tới node họ; field chung đọc thẳng từ họ. **Không đồng bộ ngầm** |
| Quyền | Giữ owner/editor/viewer + **phạm vi gia đình** từ binding đã xác minh (bản thân, vợ/chồng, cha mẹ, con cháu + vợ/chồng con cháu) |
| Ngoài phạm vi | `ChangeRequest` → editor duyệt → áp qua service sẵn có + `PersonRevision` |
| Tin cậy binding | `ClanMember.person_verified`; tự nhận = chưa xác minh, không có quyền sửa |
| Mời | Con cháu đã xác minh tự mời người trong gia đình mình (có mã ngay); vượt cấp gia đình / không gắn người → **trưởng họ hoặc Ban quản lý duyệt**; quyền editor → chỉ trưởng họ. `ClanInvite.person` → join tự bind + verified |
| Vai trò | owner (trưởng họ) > **manager (Ban quản lý, mới)**: editor toàn họ + duyệt lời mời/binding/đề xuất thay trưởng họ > editor > viewer |
| Họ lớn | Editor theo chi: `ClanMember.scope_root_person` |
| Cấu trúc | Cha/mẹ/vợ chồng mỗi cây giữ riêng; lệch → endpoint diff, không tự sửa |

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | [Pham vi quyen gia dinh va xac minh](./phase-01-pham-vi-quyen-gia-dinh-va-xac-minh.md) | Completed |
| 2 | [De xuat thay doi va duyet](./phase-02-de-xuat-thay-doi-va-duyet.md) | Completed |
| 3 | [Nhap gia pha tu may len server](./phase-03-nhap-gia-pha-tu-may-len-server.md) | Completed |
| 4 | [Lien ket ca nhan voi dong ho](./phase-04-lien-ket-ca-nhan-voi-dong-ho.md) | Completed |
| 5 | [Sua node lien ket va optimistic lock](./phase-05-sua-node-lien-ket-va-optimistic-lock.md) | Completed |
| 6 | [Editor theo chi](./phase-06-editor-theo-chi.md) | Completed |

Thứ tự phụ thuộc: 1 → 2 → 4 → 5, và 3 → 4. Phase 3 (import) độc lập, làm song song với 1–2. Phase 6 chỉ cần 1 + 2.
Phase 1 + 2 đã đủ giá trị ship riêng (chỉ đụng `/clans`).

## Ràng buộc chung

- Django app `giapha/`, MySQL 5.7 (không `WITH RECURSIVE`): mọi duyệt cây nạp in-memory (≤ 5000 người/họ, đã có `clan_edges_all`).
- File < 200 dòng, kebab-case không áp cho Python module (giữ snake_case hiện có).
- Message lỗi tiếng Việt, cùng kiểu `BadRequestException` / `PermissionDenied` hiện có.
- Mỗi phase: migration riêng, test riêng, cập nhật `docs/api-reference.md` + `docs/gia-pha-architecture.md`.
- Không phá API cũ: field mới optional, `version` check chỉ khi client gửi.

## Dependencies

- Liên quan (không chặn): `260905-1053-gia-pha-dong-ho` (completed), `260910-1622-family-api-per-user-spec` (đã ship).
- Không overlap với plan đang mở `260906-1951-remove-social-login`.

## Đã chốt (2026-09-19)

| Câu hỏi | Chốt | Phase |
|---|---|---|
| Anh chị em ruột trong phạm vi gia đình? | Có, **chỉ khi** họ chưa vào app/chưa được xác minh | 1 |
| Đề xuất để lâu? | Nhắc người duyệt ngày 7, **hết hạn ngày 30**, người gửi gửi lại được | 2 |
| Ai xác minh người tự nhận? | Trưởng họ, Ban quản lý, trưởng chi có chi chứa node | 1, 6 |
| Ghép theo tên: lệch năm sinh? | **Phải trùng năm**; thiếu năm → chỉ ghép theo cấu trúc | 4 |
| Cờ đã mất cho dòng họ? | **Thêm `Person.da_mat`**, data migration từ ngày mất hiện có | 4 |
| Import gia phả từ máy? | **Có**, phase 3 riêng trước liên kết: chỉ khi server trống, idempotent theo `importKey`, người luôn vào, cạnh lỗi bị bỏ + báo | 3 |

| Mất mạng? | **Chỉ xem**, không ghi offline | 3 |
| Chính sách quyền riêng tư? | Chủ sản phẩm cập nhật, điều kiện trước khi bật import | 3 |

Còn mở: nguồn âm lịch của app (bảng TK) có khớp Hồ Ngọc Đức UTC+7 không — kiểm bằng vector spec §7.0.

**Reports:** [Code reviewer](../reports/code-reviewer-260919-shared-clan-collaboration.md), [Tester](../reports/tester-260919-shared-clan-collaboration.md)

**Verification:** Full test suite (1110 tests, 7 skipped, 0 failures) passing on 2026-09-21. Notification delivery fixed via single `submit_change_request` entry point in `giapha/views/change_request.py`.

**Open (Low):** Import replay stale idMap; views call ORM directly (family_import.py, family_linked_edit.py); photo.py/tree.py >200 lines (pre-existing); missing query budgets for new `/clans` endpoints in test_query_counts.py.
