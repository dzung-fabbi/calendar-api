---
title: "Module Gia phả dòng họ"
description: "Django app `giapha/` — cây gia phả, lịch giỗ âm lịch VN, push nhắc giỗ, máy tính xưng hô. Backend/API only."
status: completed
priority: P1
branch: "master"
status_note: "10/10 phases shipped. All core giapha features + photos + public sharing + test coverage done."
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
| 7 | [May tinh xung ho](./phase-07-may-tinh-xung-ho.md) | Completed |
| 8 | [Presigned upload anh](./phase-08-presigned-upload-anh.md) | Completed |
| 9 | [Chia se cong khai](./phase-09-chia-se-cong-khai.md) | Completed |
| 10 | [Test hardening va docs](./phase-10-test-hardening-va-docs.md) | Completed |

## Tiến độ

**10/10 phases completed**. **720 tests pass / 4 skipped.**

Phase 8 (2026-09-06): S3 presigned upload. `giapha/services/storage.py`, `serializers/photo.py`, `views/photo.py`, `views/photo_urls.py`, 4 endpoints. Review 6.5/10 → critical photo_key bypass on `POST .../restore/{revision_id}` fixed; HIGH key-validation regex + HEAD existence test coverage + presigned-URL list minting fixed; plus 5 Lows → 9.5/10. **Real-bucket end-to-end deferred** (no S3 creds; all mock-tested).

Phase 9 (2026-09-06): Public sharing via `public_slug`. New `selectors/public.py`, `services/public_*.py`, `serializers/public.py`, `views/public.py`, migration `0006_visibility_public_link.py`. Review 7.5/10 (two PII leaks found by orchestrator, fixed) → 8.5/10 after two HIGH findings (living-person death-field all-NULL condition bypass via admin/raw update, `visibility` writable via PATCH, throttle X-Forwarded-For bypassable). **Living person's single-char given names now render as placeholder**, marriage edges omitted from public tree (product decision deferred).

Phase 7 (2026-09-05): `GET /clans/{id}/xung-ho`, 8 service modules `kinship*`. **Query budget spec ≤2 NOT MET — actual 2–4**; detail in phase file.

Phase 6: `ClanMember.person`, `GioFollow`/`DeviceToken`/`GioNotificationLog`, `remind_death_anniversary` command. **FCM real-handset criterion remains unverified** (no Firebase JSON).

Phases 1–5, 3 migrations done.

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
| PII người sống lộ qua bản công khai | **Cao** | Serializer công khai tách riêng + test security (phase 9, 10) — 3 HIGH leaks found & fixed |
| Chu trình cha-con phá mọi thuật toán duyệt | **Cao** | Validate chặn chu trình khi ghi (phase 3) |
| ~~Spam cả họ khi nhắc giỗ~~ | ~~Cao~~ **ĐÃ GỠ** | Trực hệ + override `GioFollow`, đã ship phase 6 |
| **Đường FCM chưa từng chạy thật** | **Cao** | Mock 100% → xanh. Xin Firebase JSON + run `remind_death_anniversary` để xác nhận. Tiêu chí không tick (dành smoke-test). |
| **Đường S3 chưa từng chạy thật** | **Cao** | Mock 100% → xanh (presigned PUT/HEAD/DELETE). Chưa bucket. Real upload = lần đầu với bucket thật. Tiêu chí không tick. |

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

- **Thuật toán âm lịch Hồ Ngọc Đức** — đã implement + kiểm chứng (phase 5). `giapha/services/vn_lunar.py`. Differential với `amlich.js` gốc: khớp toàn bộ **146.097 ngày 1800–2199**, hai chiều, 0 sai lệch.

  ⚠️ **ĐÍNH CHÍNH:** Tết VN 1985 = **21/01/1985**, TQ = **20/02/1985** — lệch **cả một tháng**. Các năm lệch VN/TQ: **1968, 1969, 1985, 2007**. Một báo cáo researcher từng ghi sai vì chạy reference ở tz=8 (tức lịch TQ). **Đừng "sửa" 1985 về 20/2.**
- **Hiệu năng `GET /tree`** — đã đo, đạt. Xem phase 4.
- **Xưng hô (phase 7)** — binding `ClanMember.person` cần cho phase 7 đã ship ở phase 6; phase 7 nay xong.

## Câu hỏi mở (còn lại)

Ba câu hỏi của đợt đầu (nhắc giỗ gửi cho ai / index công khai / S3 vs R2) đã chốt — xem bảng "Quyết định đã chốt (2026-09-05)" ở trên. Đánh số dưới đây độc lập với bảng đó.

### Còn lại (chuyển sang phase tiếp)

1. ~~**Ánh xạ `k` (Sóc) → số tháng âm lịch chưa chốt.**~~ **ĐÃ GIẢI QUYẾT (phase 5).** Đã implement + differential 146.097 ngày với `amlich.js` gốc, 0 sai lệch.
2. ~~**Từ xưng hô theo vùng miền.** Có cần tuỳ chọn Nam/Trung không?~~ **ĐÃ CHỐT (phase 7): chuẩn miền BẮC nghiêm**, biến thể vùng miền ngoài phạm vi. Cụ thể: anh/chị của **cả cha lẫn mẹ** → `bác`; `chú`/`cô` chỉ cho em của cha, `cậu`/`dì` chỉ cho em của mẹ. Người dùng miền Nam sẽ đọc là sai — chấp nhận.
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

### Mới phát sinh từ phase 7 (2026-09-05)

20. **`parent_kind` (`ruot`/`nuoi`/`ke`) bị bỏ qua** — con nuôi nhận đúng từ như con ruột. Gần như chắc là điều người dùng muốn (phân biệt mới là hành vi gây bất ngờ), nhưng **chưa ai chốt**; hiện là giả định ngầm trong code.
21. **Mẹ kế cố tình KHÔNG có trong bảng affinal** — cách gọi thật sự khác nhau (`mẹ`/`dì`/`mẹ kế`), chọn một là đoán. Nên rơi vào hedge "có liên kết, không có từ". Nửa máy-đọc-được của câu trả lời đó rỗng (`common_ancestor`/`path` đã null): thêm field **`via: {id, ho_ten}`** thì UI render được "vợ của Bố bạn" rồi để người dùng tự chọn. Chưa làm.
22. **Hai người CÙNG là dâu/rể** (vd. chị dâu = vợ của anh chồng) → `khong_cung_huyet_thong`. Cần hai bước hôn nhân + luật chọn đi qua vợ/chồng nào. Đã ghim bằng test, đã ghi docstring, chưa làm.
23. **`nhieu_hon_nhan_ngang_hang` có thể thành nhiễu.** Hedge này bắn khi hai hôn nhân cùng rank cho ra hai từ khác nhau — mà `Marriage.order` là **per-husband** và mặc định 1, nên hai đời chồng của một người phụ nữ đều mang `order=1`. Luật unique `order` theo từng người sẽ xoá cả lớp lỗi này — **đổi model**, ngoài phạm vi phase 7.
24. **N5 là quyết định sản phẩm do người implement tự chốt, không phải chủ dự án.** Con dâu gọi ông nội chồng là **`ông`** chứ không phải `ông nội` (lý do: `nội`/`ngoại` khẳng định huyết thống mà người đó không có; endpoint trả **cách xưng hô**, mà "ông ơi" thì ai cũng nói vậy). Nếu chủ dự án không đồng ý: xoá 4 hàng `MARRIED_IN_SUBSTITUTES`, một test lật.
25. **Điểm mù của test đối ứng đã bịt một phần, chưa hết.** Sweep chỉ ràng buộc độ sâu thang; chọn từ ở gap 0/1 do bảng `BY_HAND` giữ, và sweep hedge dùng fixture riêng — **cả hai đều mới hơn và ít trận mạc hơn** sweep từ máu mủ. Đừng coi file đối ứng là bảo chứng cho toàn bộ từ vựng.

### Mới phát sinh từ phase 8, 9, 10 (2026-09-06)

26. **`apis/views/good_day.py` `DateGoodByWorkAPIView` sắp xếp sai.** Filter `HiepKy` không `.order_by()` rồi sort chỉ có `percent` → rows cùng `percent` trả theo MySQL's arbitrary order. **Pre-existing bug, out of scope** session này. Test `apis.tests.test_api_values.test_date_good_by_work_values` fail khi chạy riêng, xanh khi chạy với các test khác (race condition, không phải timeout).

27. **Cạnh hôn nhân hiện KHÔNG xuất hiện ở bản công khai.** Phase 9 cố ý omit — `Marriage.status` có `ly_hon`/`goá`, không whitelist. Product decision: hiển thị vợ/chồng hay để họ unconnected trên public tree? Implementer call, project owner chưa chốt.

28. **Query budget `/xung-ho` ≤2 không đạt — thực tế 2–4 tuỳ luật.** `/public/tree` ≤3 không đạt — thực tế 4 (một requery per non-empty liveness branch). Có nên optimize hay revise target?

### Deferred (low-risk, documentable)

- Concurrent last-owner guard race (M2) — sequential case sẽ khoá, race-condition case tạo zero-owner clan. Chấp nhận và document.
- Concurrent generation recompute race (M6) — denormalised field, `recompute_generations` command là fixup. Chấp nhận.
- `views/params.py` consolidation (L1) — DRY-only, không behavior-change, deferred.
- Query budgets cho 12 endpoints còn lại (L4) — chỉ `/tree` có budget hiện tại.
