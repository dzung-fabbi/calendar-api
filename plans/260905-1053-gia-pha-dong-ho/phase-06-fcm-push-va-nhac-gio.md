---
phase: 6
title: "FCM push va nhac gio"
status: pending
priority: P1
effort: "2d"
dependencies: [5]
---

# Phase 6: FCM push + command nhắc giỗ

## Overview
Xây kênh gửi thông báo đẩy (chưa từng tồn tại trong codebase) và management command nhắc giỗ chạy hằng ngày.

## Key Insights — đọc trước khi bắt đầu
- **Codebase hiện KHÔNG có kênh gửi thông báo nào.** `apis/management/commands/remind_appointment_date.py` chỉ ghi log; docstring của chính nó thừa nhận "has never delivered a reminder". `settings.py` không có SMTP, FCM, Firebase hay Celery.
- **FCM legacy server key đã bị Google tắt (6/2024).** Bắt buộc dùng **FCM HTTP v1** + service account JSON + OAuth2 token. Mọi hướng dẫn cũ nói về `Authorization: key=...` đều đã lỗi thời.
- Không có Celery → command chạy bằng **cron/scheduler ngoài** (host hoặc container). Đừng thêm Celery chỉ cho một job mỗi ngày (YAGNI).

## Requirements
- Functional: client đăng ký device token; command chạy hằng ngày tìm giỗ đến hạn và gửi push; ghi log kết quả gửi; dọn token chết.
- Non-functional: command là tiến trình ngắn, idempotent trong ngày (chạy hai lần không gửi trùng); lỗi FCM của một token không làm hỏng cả lượt chạy.

## Architecture

### Model mới
```python
# giapha/models/device.py
class DeviceToken(models.Model):
    user        FK(auth.User, related_name='device_tokens')
    token       CharField(255, unique, db_index)
    platform    CharField(choices=['ios','android','web'])
    is_active   BooleanField(default=True)
    last_seen   DateTimeField(auto_now)
    created_at

# giapha/models/notification.py
class GioNotificationLog(models.Model):
    person      FK(Person)
    user        FK(auth.User)
    solar_date  DateField(db_index)     # ngày giỗ được nhắc
    sent_at     DateTimeField(auto_now_add)
    status      CharField(choices=['sent','failed'])
    error       CharField(255, blank)
    class Meta: unique_together = ('person', 'user', 'solar_date')
```
`unique_together` trên log là **cơ chế chống gửi trùng**: chạy lại command trong cùng ngày sẽ vướng constraint và bỏ qua. Đơn giản hơn nhiều so với lưu trạng thái riêng.

### Cấu hình nhắc
Thêm vào `Clan`: `gio_remind_before_days IntegerField(default=3)` — cả họ dùng chung một thiết lập. Cho phép mỗi user tự chỉnh là YAGNI ở MVP.

### Luồng command `remind_death_anniversary`
```
today = localdate()
for clan in Clan (chưa xoá):
    target = today + clan.gio_remind_before_days
    persons = người đã mất của clan có gio_solar_date(...) == target
    if không có: continue
    recipients = user của mọi ClanMember trong clan có DeviceToken active
    for (person, user): gửi push, ghi GioNotificationLog
```
Tính giỗ bằng `services/gio.py` của phase 5 — **không** đọc `AppointmentDate`, **không** materialize sẵn hàng nghìn dòng.

Tối ưu: nhóm theo clan để mỗi clan chỉ 2 query (persons đã mất + members có token). Với 1.000 clan thì là 2.000 query cho một job chạy nền — chấp nhận được, không phải request người dùng.

### Gửi FCM
`giapha/services/fcm.py`:
- Dùng `firebase-admin` (hỗ trợ Python 3.9) hoặc gọi thẳng HTTP v1 bằng `google-auth` + `requests` (đã có `requests` trong requirements).
- **Khuyến nghị: gọi thẳng HTTP v1.** `firebase-admin` kéo theo nhiều dependency; ta chỉ cần một endpoint gửi. `google-auth` là dependency nhỏ hơn nhiều.
- Gửi theo lô bằng `send_each_for_multicast` / vòng lặp có giới hạn đồng thời; token trả lỗi `UNREGISTERED` hoặc `INVALID_ARGUMENT` → set `is_active=False`.
- Credential đọc từ biến môi trường `FIREBASE_CREDENTIALS_JSON` (nội dung JSON) hoặc `FIREBASE_CREDENTIALS_PATH`. **Không commit file service account.**
- Khi thiếu credential: command log cảnh báo và thoát sạch, **không** raise — cron sẽ ồn vô ích.

### Nội dung thông báo
```
Tiêu đề: "Sắp đến ngày giỗ"
Nội dung: "Còn 3 ngày nữa là giỗ {ho_ten} (đời {generation}) — {ngày} tháng {tháng} âm lịch, nhằm {dd/mm/yyyy}."
data: {"type": "gio", "clan_id": ..., "person_id": ...}
```

## Related Code Files

**Create**
- `giapha/models/device.py`, `giapha/models/notification.py`
- `giapha/migrations/000X_devicetoken_notificationlog_remindbefore.py`
- `giapha/services/fcm.py`
- `giapha/serializers/device.py`, `giapha/views/device.py`
- `giapha/management/commands/remind_death_anniversary.py`
- `giapha/tests/test_remind_command.py`

**Modify**
- `giapha/models/clan.py` — thêm `gio_remind_before_days`
- `giapha/models/__init__.py`, `giapha/urls.py`
- `.env.example` — thêm `FIREBASE_CREDENTIALS_PATH`
- `requirements.txt` — thêm `google-auth`
- `docker-compose.yml` / `scripts/` — ghi chú cách chạy cron hằng ngày

## Endpoints
```
POST   /api/gia-pha/devices        auth, body {token, platform}   (upsert theo token)
DELETE /api/gia-pha/devices        auth, body {token}             (logout)
```

## Implementation Steps
1. Thêm model + migration. `DeviceToken.token` unique để `POST` là upsert thật.
2. Viết `services/fcm.py` với **một** hàm public `send_multicast(tokens, title, body, data) -> dict[token, ok|error]`. Tách riêng lớp lấy OAuth token (cache theo TTL, không xin token mới mỗi lần gửi).
3. Viết endpoint đăng ký/huỷ device. `POST` cùng token bởi user khác → chuyển sở hữu token sang user mới (máy dùng chung / đăng nhập lại).
4. Viết command. Cấu trúc: `collect_due(today)` (thuần, trả list việc cần gửi) tách khỏi `dispatch(jobs)` (gửi thật) → test được phần tính toán mà không đụng mạng.
5. Test command: **mock hoàn toàn lớp FCM**, không gọi mạng trong test. Phủ: đúng ngày mới gửi, chạy hai lần không gửi trùng, thiếu credential thì thoát sạch, một token lỗi không chặn các token còn lại.
6. Ghi tài liệu cách đặt cron (ví dụ `0 7 * * * python manage.py remind_death_anniversary`) vào `docs/deployment-guide.md`.
7. **Cân nhắc (không bắt buộc):** nối `apis/management/commands/remind_appointment_date.py` vào cùng `services/fcm.py` để lịch hẹn cũng gửi được push. Đây là món quà DRY rõ ràng — nhưng nó **sửa `apis/`**, nên chỉ làm khi phase 10 đã xanh, và làm thành commit riêng.

## Success Criteria
- [ ] Đăng ký device token, gửi được push thật tới một máy thử
- [ ] Command chạy 2 lần trong ngày chỉ gửi 1 lần (chặn bởi `unique_together`)
- [ ] Token chết bị đánh dấu `is_active=False` sau lần gửi lỗi
- [ ] Thiếu credential → command thoát code 0 kèm cảnh báo, không stacktrace
- [ ] Một token lỗi không làm dừng lượt gửi
- [ ] Không test nào gọi mạng thật
- [ ] Command với 100 clan chạy < 30s

## Risk Assessment
- **Đây là hạ tầng mới hoàn toàn**, không có tiền lệ trong repo để bám theo. Ước lượng 2d có thể trượt nếu khâu Firebase credential vướng thủ tục.
- **Cần tài sản bên ngoài**: Firebase project + service account JSON. Nếu chưa có, phase này **bị chặn** — xác nhận sớm, đừng để phát hiện lúc đang code.
- **Rò rỉ credential.** Service account JSON không bao giờ vào git. Thêm vào `.gitignore` ngay bước 1.
- **Spam người dùng.** Cả họ 200 người nhận push cho mọi đám giỗ của mọi chi sẽ khiến người ta tắt thông báo. Cân nhắc giới hạn: chỉ nhắc giỗ của tổ tiên trực hệ của chính người nhận. **Chưa quyết — xem câu hỏi mở của plan.**
- **Timezone — đã xác nhận là vấn đề thật.** `djangopj/settings.py:136` đặt `TIME_ZONE = 'UTC'` (với `USE_TZ = True`). Nên `timezone.localdate()` trả **ngày UTC**: cron chạy trước 07:00 giờ VN sẽ tính nhầm sang ngày hôm trước, và nhắc giỗ lệch một ngày.
  **Cách xử lý:** trong `giapha/` dùng ngày Việt Nam tường minh —
  ```python
  VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')   # pytz đã có trong requirements
  today = timezone.now().astimezone(VN_TZ).date()
  ```
  **Không** đổi `TIME_ZONE` toàn cục: `apis/` và các golden snapshot đang dựa trên hành vi hiện tại, đổi là kéo theo rủi ro ngoài phạm vi plan này.
  Ghi chú: `apis/.../remind_appointment_date.py` cũng dính đúng lỗi này — ngoài phạm vi, nhưng nên báo lại chủ dự án.
