---
title: "Module Gia phả dòng họ"
description: "Django app `giapha/` — cây gia phả, lịch giỗ âm lịch VN, push nhắc giỗ, máy tính xưng hô. Backend/API only."
status: pending
priority: P1
branch: "master"
tags: [giapha, backend, api, lunar]
blockedBy: []
blocks: []
created: "2026-09-05T04:10:12.969Z"
createdBy: "ck:plan"
source: skill
---

# Module Gia phả dòng họ

## Overview

Thêm module gia phả vào `calendar-api` dưới dạng **Django app mới `giapha/`**, tách hoàn toàn khỏi `apis/` (domain almanac). Backend/API only — client tự layout cây.

Giá trị khác biệt nằm ở chỗ app đã có lịch âm + hạ tầng nhắc: **ngày giỗ (kỵ nhật) tính theo âm lịch Việt Nam** rồi đẩy push.

Nguồn quyết định: [`plans/reports/brainstorm-260905-1053-gia-pha-dong-ho.md`](../reports/brainstorm-260905-1053-gia-pha-dong-ho.md)

## Quyết định kiến trúc đã chốt

| Hạng mục | Quyết định | Lý do |
|---|---|---|
| Vị trí code | App mới `giapha/` | `apis/` là domain almanac; trộn sẽ phá test suite hiện có |
| Quan hệ | `Person.father/mother` FK + `Marriage(order)` | KISS, phủ đa thê/tái hôn VN, ràng buộc toàn vẹn tốt |
| Duyệt cây | Nạp cả clan 1 query, duyệt Python | MySQL 5.7 **không có** `WITH RECURSIVE` |
| Âm lịch | `giapha/services/vn_lunar.py` (Hồ Ngọc Đức, UTC+7) | `lunarcalendar` là lịch TQ UTC+8, lệch 1 ngày → giỗ sai |
| Nhắc giỗ | Command tính trực tiếp + **FCM HTTP v1** | Không materialize vào `AppointmentDate` (tránh backfill) |
| Ảnh | Presigned PUT lên S3/R2 | Bytes không đi qua Django |
| Sở hữu | Clan riêng tư + tuỳ chọn `public_slug` | Ẩn chi tiết người còn sống |
| Kiếm tiền | Miễn phí, không billing | Trần `MAX_CLAN_PERSONS = 5000` chặn lạm dụng |

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | [Scaffold app va models](./phase-01-scaffold-app-va-models.md) | Completed |
| 2 | [Clan membership va phan quyen](./phase-02-clan-membership-va-phan-quyen.md) | Completed |
| 3 | [Person Marriage CRUD va validation](./phase-03-person-marriage-crud-va-validation.md) | Completed |
| 4 | [Tree endpoint va generation](./phase-04-tree-endpoint-va-generation.md) | Completed |
| 5 | [VN lunar va lich gio](./phase-05-vn-lunar-va-lich-gio.md) | Pending |
| 6 | [FCM push va nhac gio](./phase-06-fcm-push-va-nhac-gio.md) | Pending |
| 7 | [May tinh xung ho](./phase-07-may-tinh-xung-ho.md) | Pending |
| 8 | [Presigned upload anh](./phase-08-presigned-upload-anh.md) | Pending |
| 9 | [Chia se cong khai](./phase-09-chia-se-cong-khai.md) | Pending |
| 10 | [Test hardening va docs](./phase-10-test-hardening-va-docs.md) | Pending |

## Tiến độ

**4/10 phases completed** (phases 1–4 shipped, phases 5–10 pending). **261 tests green** (50 pre-existing `apis` + 211 new `giapha`). Phases 5–10 intentionally out of scope for this session; next session will resume from phase 5.

## Thứ tự phụ thuộc

```
1 ──> 2 ──> 3 ──> 4 ──> 7
              │
              └──> 5 ──> 6
              └──> 8
              └──> 9
                     └──> 10 (sau tất cả)
```

Phase 5 chỉ cần model `Person` (phase 3), không cần cây. Phase 7/8/9 độc lập nhau, chạy song song được.

## Rủi ro chính

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Âm lịch sai 1 ngày → giỗ sai | **Cao** | `vn_lunar` UTC+7 + test vectors đối chiếu (phase 5) |
| Django 3.1 EOL, Python 3.9 pin | **Cao** | Cô lập trong `giapha/`; nâng Django là việc riêng, không nhét vào plan này |
| MySQL 5.7 không có CTE đệ quy | Trung bình | Duyệt Python + trần 5.000 người/clan |
| PII người sống lộ qua bản công khai | **Cao** | Serializer công khai tách riêng + test security (phase 9, 10) |
| Chu trình cha-con phá mọi thuật toán duyệt | **Cao** | Validate chặn chu trình khi ghi (phase 3) |

## Dependencies

- Không có plan nào khác đang mở → không có phụ thuộc chéo.
- **Ngoài codebase (chặn phase tương ứng, xác nhận sớm):**
  - Firebase project + service account JSON → chặn **phase 6**
  - Bucket S3 hoặc R2 + credential + CORS → chặn **phase 8**

## Quyết định đã chốt (2026-09-05)

| # | Câu hỏi | Chốt | Ảnh hưởng |
|---|---|---|---|
| 2 | Nhắc giỗ gửi cho ai | **Trực hệ mặc định bật + cho phép user tự thêm/bớt** | Phase 6 cần bảng `GioFollow` (person, user, enabled) + duyệt tổ tiên trực hệ khi gửi |
| 3 | Bản công khai cho Google index | **Không — `noindex`** | Phase 9 giữ nguyên kế hoạch, thêm header `X-Robots-Tag: noindex` |
| 4 | S3 hay R2 | **AWS S3** | Phase 8 xin credential S3 + cấu hình CORS bucket |
| — | Phạm vi đợt này | **Phase 1–4** | Phase 5–10 để đợt sau |

## Câu hỏi mở (còn lại)

### Chốt được ở session này (phases 1–4)

| # | Câu hỏi | Chốt | Liên quan |
|---|---|---|---|
| 2 | Nhắc giỗ gửi cho ai | Trực hệ mặc định bật + cho phép user tự thêm/bớt | Phase 6 cần bảng `GioFollow` |
| 3 | Bản công khai cho Google index | Không — `noindex` | Phase 9 |
| 4 | S3 hay R2 | AWS S3 | Phase 8 |

### Còn lại (chuyển sang phase tiếp)

1. **Ánh xạ `k` (Sóc) → số tháng âm lịch chưa chốt.** Phải đối chiếu bản gốc Hồ Ngọc Đức trước khi viết phase 5. Không đoán.
2. **Từ xưng hô theo vùng miền.** MVP dùng chuẩn miền Bắc. Có cần tuỳ chọn Nam/Trung không? (phase 7)
3. **Trần 5.000 người/clan** là phỏng đoán. Dòng họ 20.000 người sẽ buộc đổi sang materialized path (đổi kiến trúc phase 4).
4. **Chính sách lưu trữ:** ai được xoá dòng họ, giữ dữ liệu bao lâu sau khi xoá? Chưa xác định.
5. **Tên huý chữ Hán-Nôm** có cần lưu không? Ảnh hưởng collation cột (`utf8_unicode_ci` hiện tại).
6. **Soft-deleted clan cascade.** Khi soft-delete một clan, có nên soft-delete tất cả persons của clan đó hay để live? Ảnh hưởng phase 9 (public page sẽ query persons).
7. **`?force=true` granularity.** Hiện tại là request-level (bulk-create 200 records cùng được force hoặc không). Nên chuyển thành per-record flag hay giữ nguyên + chỉ audit?
8. **`MAX_CLAN_PERSONS` enforcement.** API, Django admin, management command — ai nên check? Hiện tại API check, admin/command bỏ qua.
9. **Enumeration oracle trên `/join`.** Hiện tại: unknown-code → 404, expired/exhausted → 400. Tương lai: gộp thành 404 để loại bỏ oracle (sau khi throttle bật).

### Deferred (low-risk, documentable)

- Concurrent last-owner guard race (M2) — sequential case sẽ khoá, race-condition case tạo zero-owner clan. Chấp nhận và document.
- Concurrent generation recompute race (M6) — denormalised field, `recompute_generations` command là fixup. Chấp nhận.
- `views/params.py` consolidation (L1) — DRY-only, không behavior-change, deferred.
- Query budgets cho 12 endpoints còn lại (L4) — chỉ `/tree` có budget hiện tại.
