# Plan: Lịch hẹn (appointment-date) — sửa API lưu ngày + nhắc FCM hằng ngày

Ngày: 2026-09-10. Audit gốc: `plans/reports/review-260910-1823-appointment-date-reminder-api-audit.md`.
Quyết định của user: nhắc qua **FCM push**, nhắc **mỗi ngày** từ `date - before_days` tới `date`.
Kiến trúc: **cho phép `apis` import `giapha.services.fcm` + `giapha.models.DeviceToken`** (ngoại lệ
duy nhất của rule decoupling; ghi vào `docs/code-standards.md`).

## Phases
| # | Việc | Trạng thái |
|---|------|-----------|
| 1 | Serializer: `before_days` int (0..365) hai chiều, `convert_time` = cùng int; `date` bắt buộc | done |
| 2 | View: dùng `validated_data`; `id` không thuộc caller/không tồn tại → 400 (không xoá im lặng) | done |
| 3 | Model + migration 0076 `AppointmentReminderLog` (appointment, sent_on) unique → chống gửi lặp trong ngày | done |
| 4 | `services/appointment_remind.py` (pure: title/body), `selectors/appointment_remind.py` (due, already-sent) | done |
| 5 | Command `remind_appointment_date`: `today_vn()`, gửi `send_multicast`, deactivate token chết, log | done |
| 6 | Tests: management command (mock FCM), serializer round-trip, security 400, snapshots | done |
| 7 | Docs: api-reference, deployment-guide (cron), code-standards (ngoại lệ), system-architecture, codebase-summary | done |

## Semantics
- Due: `user IS NOT NULL AND date >= today AND date - before_days <= today`.
- Body: `Còn N ngày nữa đến hạn: {name} (dd/mm/yyyy).` / N=0 → `Hôm nay đến hạn: ...`.
- Không có device active → bỏ qua, không log. `send_multicast` trả `{}` → chưa cấu hình, exit 0.
- Log `sent` chặn gửi lại trong ngày; `failed` không chặn (rerun trong ngày = retry).

## Files
- Sửa: `apis/serializers/booking.py`, `apis/views/booking.py`, `apis/models/__init__.py`,
  `apis/management/commands/remind_appointment_date.py`, `apis/tests/test_management_commands.py`,
  `apis/tests/test_security.py`, `apis/tests/snapshots/{appointment_date,values_appointment_date}.json`, docs.
- Tạo: `apis/models/appointment_reminder_log.py`, `apis/migrations/0076_appointment_reminder_log.py`,
  `apis/services/appointment_remind.py`, `apis/selectors/appointment_remind.py`,
  `apis/management/commands/_appointment_reminder_log.py`, `apis/tests/test_appointment_date_api.py`.

## Review (code-reviewer, 2026-09-10)
Report: `plans/reports/code-reviewer-260910-1823-appointment-date-fcm-reminder.md`. Không Critical/High.
Đã xử lý: M1 (comment sai về IntegrityError → sửa, ghi `flock` vào deployment-guide), M2 (clamp `before_days`
cũ 0..365 bằng RunPython trong 0076), L1 docstring, L2 `id` trùng → 400, L3 đọc ownership trong transaction +
`select_for_update`, L6 docs, L7 ghi `null` → 400.
Bỏ qua (YAGNI, ghi nhận): L4 không giới hạn kích thước batch, L5 không prune log, L8-10 informational.
Test: 966/966 pass (full) trước review; 201/201 apis pass sau khi sửa theo review; `makemigrations --check` sạch.
