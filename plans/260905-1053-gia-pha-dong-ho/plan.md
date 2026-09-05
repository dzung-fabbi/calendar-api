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
| 5 | [VN lunar va lich gio](./phase-05-vn-lunar-va-lich-gio.md) | Completed |
| 6 | [FCM push va nhac gio](./phase-06-fcm-push-va-nhac-gio.md) | Completed |
| 7 | [May tinh xung ho](./phase-07-may-tinh-xung-ho.md) | Pending |
| 8 | [Presigned upload anh](./phase-08-presigned-upload-anh.md) | Pending |
| 9 | [Chia se cong khai](./phase-09-chia-se-cong-khai.md) | Pending |
| 10 | [Test hardening va docs](./phase-10-test-hardening-va-docs.md) | Pending |

## Tiến độ

**6/10 phases completed** (phases 1–6 shipped, phases 7–10 pending). **470 tests pass / 4 skipped**. Phase 5 thêm `GET /clans/{id}/lich-gio`, `services/vn_lunar.py` (UTC+7), `services/gio.py`, `services/can_chi.py`.

Phase 6 (2026-09-05) thêm `ClanMember.person`, `GioFollow`/`DeviceToken`/`GioNotificationLog`, endpoint `toi-la` + `gio-follows` + `/devices`, `services/fcm.py` + `fcm_auth.py` (HTTP v1), command `remind_death_anniversary`. Review 8.5/10, shippable. **Đúng một tiêu chí còn treo: gửi push THẬT tới máy thử — vẫn chặn bởi Firebase service account JSON**, chưa ai chạy với Firebase project thật.

Phase 7 (máy tính xưng hô) **đã gỡ chặn một nửa**: `ClanMember.person` — cái binding "tôi là ai trong cây" mà phase 7 cần — đã ship ở phase 6.

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
| ~~Âm lịch sai 1 ngày → giỗ sai~~ | ~~**Cao**~~ **ĐÃ GỠ** | `vn_lunar` UTC+7, differential 146.097 ngày với `amlich.js` gốc → 0 sai lệch (phase 5) |
| Django 3.1 EOL, Python 3.9 pin | **Cao** | Cô lập trong `giapha/`; nâng Django là việc riêng, không nhét vào plan này |
| MySQL 5.7 không có CTE đệ quy | Trung bình | Duyệt Python + trần 5.000 người/clan |
| PII người sống lộ qua bản công khai | **Cao** | Serializer công khai tách riêng + test security (phase 9, 10) |
| Chu trình cha-con phá mọi thuật toán duyệt | **Cao** | Validate chặn chu trình khi ghi (phase 3) |
| ~~Spam cả họ khi nhắc giỗ~~ | ~~Cao~~ **ĐÃ GỠ** | Trực hệ + override `GioFollow`, đã ship phase 6 |
| **Đường FCM chưa từng chạy thật** — mock xanh 100% nhưng chưa có handset nào nhận push | **Cao** | Xin Firebase JSON rồi chạy `remind_death_anniversary` một lần có người xác nhận. Không sửa code, chỉ nghiệm thu. |

## Dependencies

- Không có plan nào khác đang mở → không có phụ thuộc chéo.
- **Ngoài codebase (chặn phase tương ứng, xác nhận sớm):**
  - Firebase project + service account JSON → phase 6 đã ship không cần nó; **chỉ còn chặn đúng tiêu chí "push thật tới máy thử"**. Có JSON là chạy được ngay, không phải sửa code.
  - Bucket S3 hoặc R2 + credential + CORS → chặn **phase 8**

## Quyết định đã chốt (2026-09-05)

| # | Câu hỏi | Chốt | Ảnh hưởng |
|---|---|---|---|
| 2 | Nhắc giỗ gửi cho ai | **Trực hệ mặc định bật + cho phép user tự thêm/bớt** | Phase 6 cần bảng `GioFollow` (person, user, enabled) + duyệt tổ tiên trực hệ khi gửi |
| 3 | Bản công khai cho Google index | **Không — `noindex`** | Phase 9 giữ nguyên kế hoạch, thêm header `X-Robots-Tag: noindex` |
| 4 | S3 hay R2 | **AWS S3** | Phase 8 xin credential S3 + cấu hình CORS bucket |
| — | Phạm vi đợt này | **Phase 1–4** | Phase 5–10 để đợt sau |

## Đã gỡ chặn (2026-09-05)

- **Thuật toán âm lịch Hồ Ngọc Đức** — **đã implement + kiểm chứng** (phase 5). Công thức nay nằm trong code: `giapha/services/vn_lunar.py`, test `giapha/tests/test_vn_lunar.py`. Differential với `amlich.js` gốc: **khớp toàn bộ 146.097 ngày 1800–2199, hai chiều, 0 sai lệch**; đối sánh chéo `lunarcalendar` tz=8 (1950–2050): 0 sai lệch.

  ⚠️ **ĐÍNH CHÍNH (2026-09-05):** dòng cũ ở đây ghi "**1985 KHÔNG lệch** (cả hai 20/2)" — **SAI**. Tết VN 1985 = **21/01/1985**, TQ = **20/02/1985**, lệch **cả một tháng** (VN đặt nhuận tháng 2 Ất Sửu, TQ đặt nhuận tháng 10 Giáp Tý 1984). Các năm lệch VN/TQ: **1968, 1969, 1985, 2007**. Nguồn sai: báo cáo researcher chạy reference implementation ở **tz=8** (tức lịch TQ) — báo cáo đó nay đã có banner đính chính ở đầu file. Bản `phase-05-*.md` gốc ghi đúng ngay từ đầu. **Đừng "sửa" 1985 về 20/2.**
- **Hiệu năng `GET /tree`** — đã đo, đạt. Xem phase 4.

## Câu hỏi mở (còn lại)

Câu hỏi #2/#3/#4 đã chốt — xem bảng "Quyết định đã chốt (2026-09-05)" ở trên (không lặp lại ở đây).

### Còn lại (chuyển sang phase tiếp)

1. ~~**Ánh xạ `k` (Sóc) → số tháng âm lịch chưa chốt.**~~ **ĐÃ GIẢI QUYẾT (phase 5).** Đã implement + differential 146.097 ngày với `amlich.js` gốc, 0 sai lệch.
2. **Từ xưng hô theo vùng miền.** MVP dùng chuẩn miền Bắc. Có cần tuỳ chọn Nam/Trung không? (phase 7)
3. **Trần 5.000 người/clan** là phỏng đoán. Dòng họ 20.000 người sẽ buộc đổi sang materialized path (đổi kiến trúc phase 4).
4. **Chính sách lưu trữ:** ai được xoá dòng họ, giữ dữ liệu bao lâu sau khi xoá? Chưa xác định.
5. **Tên huý chữ Hán-Nôm** có cần lưu không? Ảnh hưởng collation cột (`utf8_unicode_ci` hiện tại).
6. **Soft-deleted clan cascade.** Khi soft-delete một clan, có nên soft-delete tất cả persons của clan đó hay để live? Ảnh hưởng phase 9 (public page sẽ query persons).
7. **`?force=true` granularity.** Hiện tại là request-level (bulk-create 200 records cùng được force hoặc không). Nên chuyển thành per-record flag hay giữ nguyên + chỉ audit?
8. **`MAX_CLAN_PERSONS` enforcement.** API, Django admin, management command — ai nên check? Hiện tại API check, admin/command bỏ qua.
9. **Enumeration oracle trên `/join`.** Hiện tại: unknown-code → 404, expired/exhausted → 400. Tương lai: gộp thành 404 để loại bỏ oracle (sau khi throttle bật).

### Mới phát sinh từ code review phase 5

10. **Múi giờ VN trước 1968.** VN dùng UTC+8 các giai đoạn 1943–45, 1947–55, 1960–67. `vn_lunar.TIMEZONE` là hằng số 7 → sai ~230 ngày trong các giai đoạn đó. **Chưa ảnh hưởng** endpoint `lich-gio` (chỉ quét tới, không đổi ngày dương lịch sử), nhưng bất kỳ tính năng "nhập ngày mất dương lịch của cụ tổ" nào cũng sẽ đụng — mà cụ tổ trước 1968 chính là dân số của app này. Cần bảng `tz_for_date()`. Đã ghi caveat trong docstring `vn_lunar.py`.
11. **`lich-gio` có nên phân trang?** Hiện bound ở `MAX_CLAN_PERSONS` + cờ `truncated` (giống `/tree`). Clan 5.000 người × cửa sổ 2 năm ≈ 10.000 item trong một response. Quyết định trước khi client ship.
12. **`death_lunar_leap` không có người dùng.** Phase 3 lưu, phase 5 cố tình bỏ qua (giỗ luôn vào tháng thường). Nếu không tính năng nào đọc thì đang lưu field chết.
13. **`giapha_person_clan_gio_idx` có thực sự được chọn không?** Chưa `EXPLAIN`. `IS NOT NULL` trên cột 2/3 kém chọn lọc; MySQL có thể dùng FK index `clan_id`. Không ảnh hưởng ở trần 5.000.

### Mới phát sinh từ phase 6 (2026-09-05)

14. ~~**NEW-2 (Medium): đọc file credential lỗi tạm thời bị xếp nhầm là "chưa cấu hình"** → bỏ dở cả lượt gửi khi xoay credential giữa chừng.~~ **ĐÃ FIX session này** — `credentials_info()` nay raise transient thay vì trả `None`. **Dư lại (perf, không phải correctness):** file service account vẫn được đọc + parse **lại mỗi recipient**; lượt gửi 500 người = 500 lần mở file cho một giá trị không thể đổi hợp lệ. Cache-cho-một-lượt-chạy là việc của phase sau.
15. **NEW-1 (Low, MỞ): `update_or_create` cho phép một lần thử FAILED sau ghi đè hàng log đang `sent`** → đẩy lại push cho người đã nhận rồi, kèm hàng audit nói dối. Cần hai lượt chạy chồng nhau; **command không giữ khoá nào** — mà `deployment-guide` nay lại bảo operator chạy lại sau sự cố. Cách chữa rẻ: loại `status='sent'` khỏi update, hoặc `flock`/khoá DB.
16. **NEW-3 (Low, MỞ): member binding vào node đã xoá mềm vẫn phân giải đủ dòng trực hệ và tiếp tục nhận push**, trong khi `toi-la` lại **từ chối TẠO** binding kiểu đó. Hai luật mâu thuẫn, không test, không doc. Chốt một hướng rồi ghim bằng test.
17. **Đổi `gio_remind_before_days` giữa năm làm nhảy qua ngày đến hạn** của bất kỳ ai rơi vào khoảng bị nhảy — người đó mất luôn lượt nhắc năm ấy. Retry của H1 **không cứu được**: họ chưa bao giờ *đến hạn*. Cần nới cửa sổ `due_rows` hoặc cảnh báo ở admin.
18. `docker-compose.yml` service `web` **đã forward** `FIREBASE_CREDENTIALS_PATH`/`_JSON` vào container (fix session này). Trước đó push thật sẽ im lặng no-op.
19. **`apis/management/commands/remind_appointment_date.py` vẫn dùng `timezone.localdate()`** — đúng lỗi lệch một ngày mà phase 6 đã né bằng `today_vn()`. Ngoài phạm vi phase 6, nhưng **chủ dự án cần quyết định có sửa không**.

### Deferred (low-risk, documentable)

- Concurrent last-owner guard race (M2) — sequential case sẽ khoá, race-condition case tạo zero-owner clan. Chấp nhận và document.
- Concurrent generation recompute race (M6) — denormalised field, `recompute_generations` command là fixup. Chấp nhận.
- `views/params.py` consolidation (L1) — DRY-only, không behavior-change, deferred.
- Query budgets cho 12 endpoints còn lại (L4) — chỉ `/tree` có budget hiện tại.
