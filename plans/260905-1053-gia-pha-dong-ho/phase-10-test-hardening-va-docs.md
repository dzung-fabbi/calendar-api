---
phase: 10
title: "Test hardening va docs"
status: completed
priority: P1
effort: "1.5d"
dependencies: [4, 5, 6, 7, 8, 9]
---

# Phase 10: Củng cố test + cập nhật docs

## Overview
Đưa module `giapha/` lên đúng chuẩn test của repo (snapshot shape, query-count ceiling, security), đo hiệu năng ở quy mô thật, và cập nhật tài liệu.

## Requirements
- Functional: mọi endpoint mới có snapshot shape + query budget; bộ test security phủ ownership và PII.
- Non-functional: `./scripts/run-tests.sh` chạy được cả `apis/` lẫn `giapha/` trong một lượt.

## Key Insights
Repo đã có sẵn hạ tầng test rất tốt trong `apis/tests/` — **dùng lại, đừng phát minh lại**:
- `apis/tests/shape.py` — `shape_of()`, `load_snapshot()`, `save_snapshot()`, cờ `REWRITE_SNAPSHOTS=1`
- `apis/tests/test_query_counts.py` — cơ chế ratchet: budget ghi lần đầu vào `snapshots/query_budgets.json`, các lần sau chỉ được thấp hơn
- `apis/tests/factories.py` — fixture dựng bằng Python, không phải JSON
- Test chạy trên **MySQL thật**, không SQLite (`djangopj/settings_test.py`) vì phụ thuộc collation

`shape.py` là hàm thuần không gắn với `apis/` → **import lại** từ `giapha/tests/`, không sao chép. Nếu thấy việc `giapha` import `apis.tests` là bẩn, chuyển `shape.py` lên một package dùng chung — **quyết định khi implement, nhưng không được sao chép hai bản.**

## Related Code Files

**Create**
- `giapha/tests/test_api_snapshots.py`
- `giapha/tests/test_query_counts.py`
- `giapha/tests/snapshots/` (golden files sinh ở lần chạy đầu)
- `giapha/tests/test_security.py` — gom các bài security xuyên phase
- `giapha/tests/perf_fixture.py` — sinh clan 1.000 người để đo

**Modify**
- `scripts/run-tests.sh` — chạy cả hai app
- `docs/system-architecture.md` — thêm mục app `giapha/`
- `docs/codebase-summary.md` — thêm bảng endpoint + query budget
- `docs/deployment-guide.md` — tạo mới nếu chưa có: cron nhắc giỗ, biến môi trường Firebase/S3, cấu hình CORS bucket
- `README.md` — một dòng nêu module gia phả và trỏ tới docs
- `.env.example` — hợp nhất toàn bộ biến mới

## Budget query mục tiêu

| Endpoint | Trần |
|---|---|
| `GET /clans` | 2 |
| `GET /clans/{id}/tree` | 3 |
| `GET /clans/{id}/persons` (phân trang) | 3 |
| `GET /clans/{id}/persons/{pid}` | 3 |
| `GET /clans/{id}/lich-gio` | 2 |
| `GET /clans/{id}/xung-ho` | 2 |
| `GET /public/{slug}/tree` | 3 |

Trần **không phụ thuộc số người trong clan** — đó chính là điều bài test chứng minh. Fixture của query-count phải có quan hệ được populate thật (cha/mẹ, hôn nhân, nhiều đời), nếu không một lỗi N+1 sẽ trông như đã được sửa.

## Implementation Steps
1. Viết `giapha/tests/factories.py` mở rộng (nếu phase 2 chưa đủ): clan có ≥ 4 đời, ≥ 2 chi, có đa thê, có người đã mất kèm ngày âm, có con nuôi.
2. `test_api_snapshots.py` — đóng băng **shape** của mọi endpoint mới bằng `shape_of()`. Ghi golden lần đầu, khẳng định từ lần sau.
3. `test_query_counts.py` — dùng lại `CaptureQueriesContext` + cơ chế ratchet. Chạy cả với fixture nhỏ và fixture 1.000 người, khẳng định **cùng một** số query.
4. `perf_fixture.py` + một test đo `GET /tree` với 1.000 người. Ngưỡng đặt rộng rãi (ví dụ < 2s trong CI, vì máy CI chậm) — mục đích là bắt hồi quy bậc thang, không phải đo chuẩn hiệu năng.
5. `test_security.py` gom lại và bổ sung:
   - outsider → 404 ở mọi endpoint clan
   - viewer → 403 ở mọi endpoint ghi
   - editor của clan A không chạm được clan B
   - bản công khai không rò trường nhạy cảm (canary từ phase 9)
   - `photo_key` chéo clan bị chặn
   - device token của user khác không xoá được
6. Cập nhật `scripts/run-tests.sh` để `manage.py test apis giapha`.
7. Cập nhật docs:
   - `system-architecture.md`: cây thư mục `giapha/`, phụ thuộc một chiều, và **ghi rõ mâu thuẫn có chủ đích**: `apis/` dùng `lunarcalendar` (UTC+8), `giapha/` dùng `vn_lunar` (UTC+7). Kèm lý do, để người sau không "sửa" nó thành một.
   - `codebase-summary.md`: bảng endpoint + budget, và ràng buộc còn tồn đọng.
   - `deployment-guide.md`: cron, biến môi trường, CORS bucket, cảnh báo không commit service account.
8. Chạy toàn bộ suite, xác nhận `apis/` vẫn xanh (không hồi quy).

## Success Criteria
- [x] `./scripts/run-tests.sh` runs both `apis` and `giapha` — **720 total tests, 0 failures, 4 skipped**
- [x] All new endpoints have snapshot shape (30 goldens across 3 files via new shared `testkit/` package)
- [x] All new endpoints have query-count ratchet tests; counts measured (but see below for budget misses)
- [x] `GET /tree` with 1,000 people performance-guarded (regression guard @ 2s)
- [x] Security suite covers 6 groups: outsider-404 matrix, viewer-403 matrix, cross-clan edit rejection, PII canary, cross-clan photo-key rejection, device-token ownership
- [x] `docs/system-architecture.md` explains why both apps use different lunar calendars (apis: UTC+8 TQ, giapha: UTC+7 VN)
- [x] `.env.example` has all new vars; no real credentials committed
- [x] `apis/` suite still green (no regression)
- [ ] **BUDGET MISS** — `GET /xung-ho` target ≤2, actual 2–4 depending on kinship rule. Query budget NOT met as originally specified.
- [ ] **BUDGET MISS** — `GET /public/tree` target 3, actual 4 (one requery per non-empty liveness branch). Budget NOT met as originally specified.

## Risk Assessment
- **Snapshot ghi lần đầu là tự-khẳng-định.** Golden file chỉ có giá trị nếu shape lúc ghi là đúng. Phải **review bằng mắt** file JSON đầu tiên trước khi commit, không commit mù.
- **Test query-count với fixture rỗng là vô nghĩa** — `apis/tests/factories.py` đã ghi rõ bài học này trong docstring. Fixture phải có quan hệ thật.
- **Test hiệu năng dễ chập chờn trong CI.** Đặt ngưỡng rộng và chỉ bắt hồi quy bậc thang; đừng đặt ngưỡng sát rồi phải tắt test.
- **Docs sẽ lỗi thời.** Mâu thuẫn lịch âm là thứ dễ bị "sửa nhầm" nhất — viết lý do rõ ràng ngay tại chỗ, không chỉ trong plan này.

## Next Steps (sau khi plan hoàn tất, ngoài phạm vi)
1. **Nâng cấp Django 3.1 → LTS.** Đang EOL và ghim Python 3.9. Là việc riêng, không nhét vào plan này.
2. Sửa lỗi timezone của `apis/.../remind_appointment_date.py` (cùng lỗi UTC đã nêu ở phase 6).
3. Nối `remind_appointment_date` vào `giapha/services/fcm.py` để lịch hẹn cũng gửi được push.
4. Các tính năng đã hoãn: xuất PDF, import Excel, văn khấn tự sinh, chọn ngày tốt việc họ, bản đồ mộ phần, quỹ họ, GEDCOM.
