# Audit: API lưu ngày & nhắc ngày (appointment-date)

Ngày: 2026-09-10. Phạm vi: `GET/POST /api/appointment-date`, model `AppointmentDate`,
command `remind_appointment_date`. Đã chạy probe thật trên MySQL 5.7 (docker), 8/8 test hiện có pass.

## Kết luận
**Lưu ngày: đúng nhưng chưa đủ (1 lỗi 500).** **Nhắc ngày: CHƯA hoạt động** — command chỉ log, không gửi gì, không có cron.

## Đã đúng
- Ownership: chỉ thấy/sửa/xoá row của chính mình; `user_id` client gửi bị bỏ qua (test_security pass).
- Validate `date` sai format → 400; `name` rỗng → 400; body không phải list → 400.
- Query budget GET = 1; POST chạy trong `transaction.atomic`.
- Command tính đúng `date - before_days == today` (test pass, kể cả before_days=0).

## Lỗi / thiếu (theo mức độ)
| # | Mức | Vấn đề | Bằng chứng |
|---|-----|--------|-----------|
| 1 | Cao | **Không có gửi nhắc**. `remind_appointment_date` chỉ `logger.info`, không push/email. Không có cron trong `docs/deployment-guide.md` (chỉ có `remind_death_anniversary`). | `apis/management/commands/remind_appointment_date.py` docstring tự ghi INCOMPLETE |
| 2 | Cao | **Round-trip 500**: server trả `before_days: "3 00:00:00"`, client gửi lại y nguyên → `int("3 00:00:00")` ValueError → 500. | probe: POST lại response của GET → 500 |
| 3 | Trung | Command dùng `timezone.localdate()` với `TIME_ZONE=UTC` → cron chạy trước 07:00 VN tính nhầm sang hôm trước. Giapha đã sửa bằng `services.gio.today_vn()`. | `remind_appointment_date.py:27` |
| 4 | Trung | Item có `id` lạ/stale (đã xoá, của người khác) bị **bỏ im lặng**, đồng thời bước xoá vẫn chạy → mất dữ liệu không báo. | probe: POST `[{"id":999999,...}]` → 201 `{"data": []}` |
| 5 | Trung | `before_days` không kiểm tra miền: `-2` được lưu; `1.5` bị cắt thành 1; `"3"` serializer hiểu là 3 giây nhưng view lưu 3 ngày. Không có giới hạn max. | probe |
| 6 | Thấp | `date` cho phép `null` và ngày quá khứ → row không bao giờ nhắc, không cảnh báo. | probe |
| 7 | Thấp | Không chặn trùng (2 row cùng name+date), không có `updated_at`, không đánh dấu "đã nhắc" (giapha có `GioNotificationLog` để chống gửi lặp). | probe dup=2 |
| 8 | Thấp | `convert_time` trả `"259200.0"` (giây dạng chuỗi) — thừa, khó dùng; docs nói "cùng giá trị" với `before_days` nhưng thực tế khác format. | response |
| 9 | Thấp | Model không có trường phân loại (đăng kiểm/bảo hiểm/bằng lái…), không có `note`/`repeat` → "ngày xe" lặp hằng năm phải tạo lại tay. | model |

## Đề xuất sửa (thứ tự)
1. Serializer: `before_days = IntegerField(min_value=0, max_value=365)`; `to_representation` trả int ngày; bỏ `convert_time` hoặc trả cùng int. Client gửi lại được (fix #2, #5, #8).
2. View: id không thuộc caller → 400 `{"id": "..."}` thay vì bỏ qua (fix #4).
3. Command: dùng `today_vn()`; nối `giapha.services.fcm.send_multicast` + `DeviceToken` (đã có sẵn) + bảng log chống gửi lặp; thêm cron vào deployment-guide (fix #1, #3).
4. Tuỳ chọn: `date` not-null, từ chối ngày quá khứ khi tạo mới; thêm `kind`/`repeat_yearly`.

## Câu hỏi chưa chốt
- Kênh nhắc mong muốn: FCM push (đã có hạ tầng giapha), email, hay in-app list?
- Nhắc 1 lần đúng ngày `date - before_days`, hay nhắc mỗi ngày từ đó tới `date`?
- "Ngày xe" có cần lặp hằng năm (đăng kiểm/bảo hiểm) không?
