# Tài Liệu API

Tài liệu bao gồm ba nhóm, theo thứ tự trong file:

| Nhóm | Mount | Nguồn |
|---|---|---|
| Đăng nhập / đăng xuất (JWT) | `/api/auth/` | app `apis/` |
| Tài khoản, tải tệp, lịch vạn niên, đặt lịch | `/api/` | app `apis/` |
| Gia phả cộng tộc (26 endpoint) | `/api/gia-pha/` | app `giapha/` |
| Gia phả cá nhân (13 endpoint) | `/api/gia-pha/v1/family/` | app `giapha/` |

Đường dẫn gốc mặc định của phần gia phả: `/api/gia-pha/`. Endpoint của `apis/` luôn ghi đủ tiền tố `/api/`.

## Xác Thực

Tất cả endpoint cần token JWT bearer (trừ public endpoint ghi chú riêng):
```
Authorization: Bearer {access_token}
```

**Các endpoint xác thực** (app `apis/`, mount ở `/api/auth/`):

| Endpoint | Dùng khi | Body | Thành công |
|---|---|---|---|
| `POST /api/auth/login` | Đăng nhập bằng username/password | `username`, `password` | 200 `{access_token, refresh_token, token_type:"Bearer", expires_in}` |
| `POST /api/auth/refresh` | Làm mới access token | `refresh_token` | 200 (cùng format, token mới) |
| `POST /api/auth/logout` | Đăng xuất | `refresh_token` | 204 (body trống) |

**Ghi chú:**
- Cả ba endpoint chấp nhận body dạng `application/x-www-form-urlencoded` hoặc JSON (`application/json`).
  Body JSON không phải object (mảng, chuỗi, số, `null`) → 400, không 500.
- **Access token là JWT HS256**, mặc định sống **1 giờ** (`expires_in` trong response tính bằng giây).
- **Refresh token là chuỗi ngẫu nhiên 32 byte**, lưu **dưới dạng băm sha256** trong database, **dùng một lần**.
  Mỗi lần gọi `/api/auth/refresh` trả về refresh token mới và **xoá token cũ khỏi database**.
- Sai username/password / tài khoản bị khoá / refresh token hỏng-hết hạn-đã dùng → **401** với
  một thông báo chung (không phân biệt được, cố ý).
- Thiếu field bắt buộc → 400 `{"field": ["error message"]}`.
- **Đổi mật khẩu làm mọi access token hết hiệu lực ngay** (không chờ hết 1 giờ), vì access token
  có claim `pwd` = sha256 của mật khẩu hiện tại. Refresh token cũ cũng bị xoá.

### ⚠️ Chuyển đổi từ `/auth/token` (BREAKING)

Các URL cũ `/auth/token` và `/auth/revoke-token` **trả 404**. Mọi client đã phát hành phải:
1. Gọi `/api/auth/login` với `username`/`password` thay vì `/auth/token` (bỏ hẳn `client_id`/`client_secret`/`grant_type`)
2. Gọi `/api/auth/refresh` thay vì `/auth/token` với `grant_type=refresh_token`
3. Gọi `/api/auth/logout` với `refresh_token` thay vì `/auth/revoke-token`

**Mọi người dùng phải đăng nhập lại sau deploy** — tất cả access token và refresh token cũ bị vô hiệu.

### Bao Đóng Response

Hầu hết endpoint trả về response bao trong `{"data": ...}`. **Ngoại lệ:**
- **204 No Content** (DELETE) không có body
- Validation errors (400) trả dict lỗi trực tiếp, không bao
- Ba endpoint xác thực `/api/auth/login`, `/api/auth/refresh`, `/api/auth/logout` trả payload phẳng, không bao
- Bốn endpoint gia phả cộng tộc trả payload phẳng, không bao: `/clans/{id}/tree`, `/clans/{id}/lich-gio`,
  `/clans/{id}/gio-follows`, `/clans/{id}/xung-ho`, và public `/public/{slug}/tree`
- **Mười ba endpoint gia phả cá nhân** (`/v1/family/*`) trả payload phẳng, không bao (xem phần "Gia Phả Cá Nhân" bên dưới)
- `/public/{slug}/persons/{person_id}` **có** bao `{"data": person}` (khác với public tree)
- Ở `apis/`: `GET /api/so-hoc`, `GET /api/than-sat` và `POST /api/book-calendar` trả dữ liệu trực tiếp, không bao

## ⚠️ Thay Đổi Không Tương Thích: Danh Sách Thành Viên Họ

`GET /api/gia-pha/clans/{id}/members` (và các response chứa `ClanMember`) **không còn trả
`username`** cho `editor`/`viewer` — chỉ `owner` mới thấy. Thay vào đó có trường mới
**`display_name`** (họ + tên; nếu tài khoản chưa đặt tên thì là dạng che `ngu***`).

**Lý do:** đăng ký tài khoản lưu email làm `username`. Serializer vốn đã cố ý giấu `email`
với người không phải chủ họ, nhưng vẫn trả `username` — nên nếu giữ nguyên, một `viewer` vào
họ bằng invite code sẽ lấy được đúng danh sách email mà cái khoá kia sinh ra để bảo vệ.

**Client cần làm:** đổi chỗ hiển thị `username` sang `display_name`.

## Tải Tệp Lên (`/api/files/`)

Endpoint dùng chung, **không gắn** với model nào — không ghi DB, không lưu lịch sử. Nằm ở
app `apis/`, dùng chung 5 biến `S3_*` với phần ảnh gia phả (xem `docs/deployment-guide.md`).

| Endpoint | Auth | Body | Thành công |
|---|---|---|---|
| `POST /api/files/upload-url` | không | `content_type`, `size` | 200 `{"data": {"upload_url", "key", "expires_in": 300}}` |
| `POST /api/files/confirm` | không | `key` | 200 `{"data": {"key", "url", "expires_in": 3600}}` |

### Luồng 2 bước

**Byte của tệp không bao giờ đi qua Django** — client `PUT` trực tiếp lên S3/R2. Đẩy byte
qua Django sẽ giữ chặt một gunicorn worker suốt thời gian upload.

```
1) POST /api/files/upload-url   {"content_type": "image/jpeg", "size": 123456}
   -> {"data": {"upload_url": "https://...", "key": "uploads/<32 hex>.jpg", "expires_in": 300}}

2) PUT <upload_url>             (byte của tệp; header Content-Type PHẢI khớp content_type đã khai)

3) POST /api/files/confirm      {"key": "uploads/<32 hex>.jpg"}
   -> {"data": {"key": "...", "url": "<presigned GET>", "expires_in": 3600}}
```

Client **lưu `key`**, gọi lại `confirm` để lấy URL mới khi link hết hạn.

**Client chạy trong trình duyệt:** bước 2 `PUT` đi thẳng tới bucket, nên bucket phải có
CORS rule cho phép `PUT` + header `Content-Type` từ origin của app. Thiếu rule thì browser
chặn request với lỗi CORS không có body — đây là lỗi setup phổ biến nhất. Một rule dùng
chung cho cả `/api/files` lẫn ảnh gia phả (cùng bucket); xem `docs/deployment-guide.md`.

### Giới hạn

- **Chỉ ảnh:** `image/jpeg`, `image/png`, `image/webp`. Type khác → 400.
- **Tối đa 5MB.** `size` ở bước 1 chỉ là *khai báo* của client, dùng để chặn sớm. Presigned
  `PUT` về bản chất **không** chặn được kích thước trước (không có `content-length-range`),
  nên cap được thực thi thật ở bước `confirm`: server `HEAD` object và đọc `ContentLength`
  thực tế. Client khai 1KB rồi push 10MB vẫn bị từ chối ở bước 3.
- `confirm` cũng kiểm **`ContentType` thật của object**, không tin cái client khai ở bước 1.
- `key` phải đúng hình dạng server sinh ra: `uploads/{32 ký tự hex}.{jpg|png|webp}`. Mọi
  thứ khác (traversal `../`, thiếu đuôi, đuôi lạ, chữ hoa, thư mục con) → 400, và **không**
  chạm tới S3.
- Chưa cấu hình `S3_*` → **503** ở cả hai endpoint. Phần API còn lại không ảnh hưởng.
- URL trả về là **presigned GET, hết hạn sau 1 giờ**. Bucket là private — không có URL công
  khai vĩnh viễn.

### ⚠️ Không yêu cầu xác thực

Cả hai endpoint là `AllowAny`, chỉ có throttle **20 lần/giờ** (scope `file-upload`, dùng
chung cho cả hai). Nghĩa là **bất kỳ ai cũng ghi được object vào bucket**.

Throttle này không phải rào cản thật, và con số "20/giờ" cần đọc kỹ:

- Bucket throttle là **mỗi IP** với caller ẩn danh, nhưng **mỗi user** nếu request có Bearer
  token hợp lệ (`SimpleRateThrottle.get_cache_key`).
- Per-IP chỉ có ý nghĩa khi `DJANGO_NUM_PROXIES` khớp số proxy tin cậy thật (mặc định `0`);
  và đủ nhiều IP nguồn thì vượt qua được.
- Project **không cấu hình `CACHES`** → Django dùng `LocMemCache`, **không chia sẻ giữa các
  process**. Với N gunicorn worker, trần thực tế là **20 × N** mỗi IP.

Allowlist chỉ-ảnh giảm nhẹ, nhưng cần chính xác về việc nó mua được gì: nó ràng buộc
**`Content-Type` mà object được trả về**, *không* ràng buộc nội dung. `confirm` kiểm nhãn
`Content-Type` qua `HEAD`; **không có chỗ nào đọc byte** của file (thiết kế presigned không
làm được). Kẻ lạ vẫn lưu được payload 5MB tuỳ ý dán nhãn `image/png`. Cái nó chặn là payload
đó **được serve như** `text/html` / `image/svg+xml` — tức chặn thực thi script trên origin
của bucket. Mở rộng allowlist mà không thêm auth là cho đi đúng thứ đó.

Object mồ côi (xin `upload-url` rồi không `confirm`) **không có job nào dọn**. Nên đặt
lifecycle rule cho prefix `uploads/` trên bucket.

## Tài Khoản (`/api/`)

Các endpoint quản lý tài khoản nằm ở app `apis/`, **không** phải `/api/gia-pha/`. Ghi ở đây
vì chúng bổ sung cho phần "Xác Thực" bên trên: `/api/auth/login` cấp token, nhóm này lo phần
còn lại của vòng đời tài khoản.

| Endpoint | Auth | Body | Thành công |
|---|---|---|---|
| `POST /api/auth/register` | không | `email`, `password`, `first_name?`, `last_name?` | 201 `{"data": <user>}` |
| `POST /api/auth/forgot-password` | không | `email` | 200 `{"data": {"detail": "..."}}` |
| `POST /api/auth/verify-otp` | không | `email`, `code` | 200 `{"data": {"valid": true}}` |
| `POST /api/auth/reset-password` | không | `email`, `code`, `new_password` | 200 `{"data": {"detail": "..."}}` |
| `POST /api/auth/change-password` | Bearer | `current_password`, `new_password` | 200 `{"data": {"detail": "..."}}` |
| `GET /api/me` · `GET /api/get-user` | Bearer | — | 200 `{"data": <user>}` |
| `PATCH /api/me` · `PATCH /api/get-user` | Bearer | `first_name?`, `last_name?`, `phone?`, `birth_date?`, `avatar_url?` | 200 `{"data": <user>}` |

`/api/me` và `/api/get-user` là **cùng một view**. `get-user` là tên cũ, giữ cho client đã
phát hành; `me` là tên nên dùng cho client mới.

**`<user>`:**

```json
{"id": 1, "username": "a@b.com", "email": "a@b.com",
 "first_name": "An", "last_name": "Nguyễn",
 "date_joined": "...", "last_login": "...",
 "profile": {"phone": "0912345678", "birth_date": "1990-01-31", "avatar_url": "https://..."}}
```

`profile` luôn có mặt. Tài khoản cũ hơn migration 0055 chưa có bản ghi profile sẽ nhận
`{"phone": "", "birth_date": null, "avatar_url": ""}` chứ không phải lỗi.

### Đăng ký

- **Email chính là định danh đăng nhập**: lưu vào cả `username` lẫn `email`, chuẩn hoá về
  chữ thường. Đăng ký xong dùng ngay `/api/auth/login` với `username`/`password`, không có bước
  xác minh email.
- Email tối đa **150 ký tự** (giới hạn của cột `auth_user.username`, không phải 254 của `email`).
- Mật khẩu chạy qua `AUTH_PASSWORD_VALIDATORS` của Django, gồm cả kiểm tra "quá giống email/tên".
- Ký tự ngoài BMP (emoji) trong tên bị từ chối 400: MySQL 5.7 ở đây chạy `utf8` 3 byte,
  không lưu được ký tự 4 byte.

### Quên mật khẩu (OTP 6 số)

1. `POST /api/auth/forgot-password` → mã 6 số gửi qua email, **hiệu lực 10 phút**.
2. `POST /api/auth/verify-otp` (tuỳ chọn) → kiểm tra mã mà **không tiêu** nó. Dùng để báo
   "sai mã" ngay ở màn hình nhập mã. Đoán sai ở đây **vẫn bị tính** vào số lần thử.
3. `POST /api/auth/reset-password` → đặt mật khẩu mới.

**Client cần biết:**

- `forgot-password` **luôn trả 200 với nội dung giống hệt nhau**, kể cả khi email không tồn
  tại, tài khoản bị khoá, đã vượt hạn mức, hoặc gửi mail thất bại. Đây là cố ý — phản hồi
  khác nhau sẽ biến endpoint thành công cụ dò xem một địa chỉ có phải người dùng hay không.
  **Đừng hiển thị "email không tồn tại"** dựa trên endpoint này; nó không bao giờ nói thế.
- Mã **sai 5 lần là chết**, kể cả sau đó nhập đúng — phải xin mã mới. Khoá theo **mã**, không
  theo tài khoản (khoá theo tài khoản sẽ cho phép bất kỳ ai khoá người khác chỉ bằng email).
- Xin mã mới sẽ **vô hiệu hoá mã cũ**. Tối đa **3 lần/giờ mỗi tài khoản**.
- Mọi lỗi mã (sai / hết hạn / đã dùng / hết lượt / email lạ) trả về **cùng một body**.
- Tài khoản không có mật khẩu dùng được (`set_unusable_password()`) **đặt lại được** qua luồng
  này — đây là đường phục hồi duy nhất của chúng.

### Đổi mật khẩu và thu hồi token

**`reset-password` và `change-password` đều xoá TOÀN BỘ refresh token của tài khoản** và làm
**mọi access token hết hiệu lực ngay** (thay vì chờ hết 1 giờ) — kể cả token đang gọi chính request đó.
Sau khi nhận 200, client **phải đăng nhập lại**; token cũ sẽ trả 401 ở request kế tiếp. Đây là hành vi cố ý:
đổi mật khẩu vì bị lộ thì phải đẩy được kẻ đang giữ token ra ngoài.

### Sửa thông tin cá nhân

- `email` và `username` **không sửa được** và bị **bỏ qua im lặng** trên PATCH. Chúng là định
  danh đăng nhập và chưa có bước xác minh địa chỉ, nên cho sửa đồng nghĩa với việc ai chiếm
  được token có thể trỏ tài khoản về hộp thư của mình rồi dùng "quên mật khẩu" để khoá chủ
  tài khoản vĩnh viễn. Muốn đổi email: liên hệ quản trị viên.
- `phone`: định dạng Việt Nam, chấp nhận `0…`, `+84…`, có khoảng trắng/gạch nối. Chuỗi rỗng xoá giá trị.
- `birth_date`: `YYYY-MM-DD`, không được ở tương lai. `null` xoá giá trị.
- `avatar_url`: **client tự upload ảnh ở nơi khác rồi gửi URL về**. API không nhận bytes ảnh.
  Chỉ chấp nhận `http`/`https` — `javascript:`/`data:` bị từ chối 400.
- Trường vắng mặt trong body thì **giữ nguyên** giá trị đang lưu (đúng ngữ nghĩa PATCH).

### Throttle của nhóm tài khoản

`auth-register` 10/giờ · `auth-forgot-password` 5/giờ · `auth-reset-password` 10/giờ ·
`auth-change-password` 10/giờ.

Ba scope đầu tính **theo IP** và chỉ là rào cản chi phí — xem cảnh báo `NUM_PROXIES` ở
`djangopj/settings.py`. Thứ thực sự chặn dò mã là bộ đếm số lần thử trên từng mã và hạn mức
3 lần/giờ mỗi tài khoản. `auth-change-password` tính **theo người dùng** (đã xác thực) nên
chặt hơn hẳn.

## Lịch Vạn Niên & Đặt Lịch (`/api/`)

Nhóm endpoint gốc của app `apis/` (tra cứu hiệp kỷ, tiết khí, thần sát, số học, ngày tốt).
Project **không đặt `DEFAULT_PERMISSION_CLASSES`**, nên view nào không khai báo quyền là
`AllowAny`. Không throttle. Tất cả tham số truyền qua **query string** (kể cả `calendar`).

| Endpoint | Auth | Tham số | Thành công |
|---|---|---|---|
| `GET /api/home` | không | `lunar_day` (can chi ngày, vd `Giáp Tý`), `tiet_khi`, `month` (int), `lunar_date` (`YYYY-MM-DD HH:MM:SS`) — đều bắt buộc | 200 `{"data": {"hiep_ky", "tiet_khi", "hour_in_days", "quy_nhan": [], "tu_dai": []}}` |
| `GET /api/tiet-khi` | không | `tiet_khi` (tên tiết khí) | 200 `{"data": {"tiet_khi", "start_time", "end_time"}}` — bản ghi của **năm hiện tại**; không có → `{"data": null}` |
| `GET /api/calendar` | không | `data` = **chuỗi JSON** mảng `[{"month": 1, "lunar_day": "Giáp Tý"}, ...]` | 200 `{"data": [{"should_things", "no_should_things", "good_stars", "ugly_stars"}]}` — cùng thứ tự input; ngày không có dữ liệu → 4 chuỗi rỗng |
| `GET /api/than-sat` | không | `year` | 200 `{"than_sat_by_year", "than_sat_by_month"}` (**không bao `data`**) |
| `GET /api/so-hoc` | không | `birth_day` (`DDMMYYYY`, đúng 8 chữ số), `full_name`, `phone` (chỉ chữ số) | 200 object phẳng, **không bao `data`** (xem bên dưới) |
| `GET /api/get-date-good-by-work` | không | `work` (tên việc, tuỳ chọn), `month`, `year` (int) | 200 `{"data": [{"month", "work", "lunar_day", "lunar_date", "percent", "text"}]}` sắp theo `percent` giảm dần |
| `GET /api/get-config` | không | — | 200 `{"data": {"date_config", "hours_config", "direction_config"}}` (bản ghi mới nhất mỗi bảng) |
| `POST /api/book-calendar` | không | body `{work, date, email?}` | 201 `{work, date, email}` (**không bao `data`**) |
| `GET /api/appointment-date` | Bearer | — | 200 `{"data": [appointment, ...]}` của chính caller |
| `POST /api/appointment-date` | Bearer | body **mảng** `[{id?, name, date, before_days}]` | 201 `{"data": [appointment, ...]}` |
| `GET /api/get-bank` | Bearer | — | 200 `{"data": {"bank": {...}, "code": "ABCDEF"}}` |

**Ghi chú:**

- Thiếu/sai tham số → 400 `{"detail": "Tham số 'x' không hợp lệ: <lý do>"}`.
- `get-date-good-by-work`: `work` khớp `icontains` với `should_things`; alias `Tu tạo mồ mả` →
  `Tu Tạo Động Thổ`. Ngưỡng đánh giá lấy từ `DateConfig` (admin sửa được).
- `so-hoc` trả: `so_chu_dao`, `so_thai_do`, `so_ngay_sinh`, `so_no_nghiep` (mảng), `so_nam_ca_nhan`,
  `so_thang_ca_nhan`, `tuoi_dinh_cao_1..4`, `dinh_cao_1..4`, `thu_thach_1..4`, `so_su_menh`, `so_linh_hon`,
  `so_nhan_cach`, `so_truong_thanh`, `so_phat_trien`, `so_noi_cam`, `the_nhan_dang`, `so_thieu` (luôn `""`),
  `so_dien_thoai`.
- `POST /api/appointment-date` là **thay thế toàn bộ** danh sách của caller: item có `id` thuộc caller →
  cập nhật; không có `id` → tạo mới; bản ghi cũ không xuất hiện trong body → **xoá**. `id` không tồn tại
  hoặc của người khác → **400** `{"detail": "Lịch hẹn không tồn tại hoặc không thuộc bạn: <ids>"}`, cả batch
  không đổi (một thông điệp chung, không lộ id của người khác có tồn tại hay không). `date` bắt buộc
  (`YYYY-MM-DD`). `before_days` là **số ngày nguyên 0..365**, mặc định 0, **cùng dạng int ở cả request và
  response** (trước 2026-09-10 response trả `"3 00:00:00"` và gửi lại y nguyên gây 500); bỏ trống → 0,
  nhưng `null` → 400. Hai item cùng `id` trong một body → 400. `convert_time` là
  alias cũ, cùng int với `before_days`. Item trả về: `id`, `name`, `date`, `before_days`, `user_id`,
  `convert_time`.
- **Nhắc lịch hẹn qua FCM, mỗi ngày cho tới hạn:** cron `manage.py remind_appointment_date` chạy mỗi sáng
  (giờ VN) đẩy push tới mọi thiết bị active của chủ lịch (token đăng ký qua `POST /api/gia-pha/devices`)
  trong cửa sổ `date - before_days ≤ hôm nay ≤ date`. Title `Sắp đến hạn lịch hẹn`; body
  `Còn N ngày nữa đến hạn: {name} (dd/mm/yyyy).` hoặc `Hôm nay đến hạn: ...`; `data`
  `{type: "appointment", appointment_id, date}` (chuỗi). Mỗi lịch hẹn tối đa một push/ngày
  (`AppointmentReminderLog`). Không có thiết bị → không gửi, không lỗi. Xem `docs/deployment-guide.md`.
- `get-bank`: `bank` là cấu hình chuyển khoản (`account_number`, `account_holder`, `bank`, `branch`,
  `qr_img`); `code` là mã tham chiếu 6 chữ in hoa của giao dịch đang chờ — gọi lại trả **cùng một `code`**
  cho tới khi giao dịch được duyệt.

## Mô Hình Phân Quyền

**Ba vai trò:** `owner` (quản trị họ), `editor` (viết person/marriage), `viewer` (chỉ đọc).

**Quan trọng:** Người ngoài họ nhận **404 Not Found**, không bao giờ 403 Forbidden. 403 sẽ xác nhận họ tồn tại.

**Cấp `owner`:** invite code chỉ cấp tối đa `editor`/`viewer`, không bao giờ `owner`. Owner hiện tại có thể
nâng một thành viên khác lên `owner` qua `PATCH /clans/{id}/members/{user_id}` với `{"role": "owner"}`
(một họ có thể có nhiều owner). Không hạ được owner cuối cùng.

## Throttle (Giới Hạn Tần Suất)

- **`POST /api/auth/login`** (`auth-login` scope): 20 yêu cầu/giờ mỗi IP
- **`POST /api/auth/refresh`** (`auth-refresh` scope): 60 yêu cầu/giờ mỗi IP
- **`POST /api/auth/logout`** không giới hạn (token 256-bit không đoán được)
- **`POST /join`** (`giapha-join` scope): 10 yêu cầu/giờ mỗi IP
- **Public tree/person endpoints** (`giapha-public` scope): 60 yêu cầu/giờ mỗi IP
- **`POST /api/files/upload-url` + `POST /api/files/confirm`** (`file-upload` scope): 20
  yêu cầu/giờ, **dùng chung một bucket** cho cả hai endpoint. Ẩn danh → bucket theo IP; có
  Bearer hợp lệ → bucket theo user. `LocMemCache` không chia sẻ giữa worker nên trần thực
  tế là 20 × số worker
- **Endpoint tài khoản khác** (`apis/`): `auth-register` 10/giờ, `auth-forgot-password` 5/giờ,
  `auth-reset-password` 10/giờ, `auth-change-password` 10/giờ

Bucket là **mỗi IP** (từ `X-Forwarded-For` nếu `DJANGO_NUM_PROXIES` khớp deployment; nếu không dùng `REMOTE_ADDR`). Đây là tăng chi phí, không phải hard stop.

## Các Quy Tắc Chéo & Semantic Quan Trọng

### 1. Generation là Dữ Liệu Derived, Read-Only

`generation` trong response được tính từ cây. POST `generation: 999` bị bỏ qua im lặng, không lỗi.

### 2. Upload Ảnh: Ba Bước Presigned

Không thể upload ảnh qua `PATCH /persons/{pid}`. Quy trình:

1. **`POST .../photo-upload-url`** — request `{content_type, size}`, nhận presigned `PUT` URL + key
   - Content type cho phép: `image/jpeg`, `image/png`, `image/webp`
   - Max size hint: 5 MB (chỉ khai báo client; thực tế kiểm tra ở bước 3)
   - Response: `{data: {upload_url, key, expires_in: 300}}`
   - TTL PUT: 300 giây

2. **Client PUT bytes trực tiếp tới presigned URL** (ngoài Django)
   - Header `Content-Type` chính xác (từ bước 1)
   - Không enforce size ở đây

3. **`POST .../photo` confirm** — request `{key}`, khóa ảnh
   - Validate key shape: `giapha/{clan_id}/{person_id}/{32-hex-uuid}.{jpg|png|webp}`
   - HEAD object (kiểm tra tồn tại, size, content-type)
   - **Enforce 5 MB ở đây**
   - Response: `{data: person_serialized_with_photo_url}`

**Lưu trữ không cấu hình?** Ba endpoint ảnh trả 503 Service Unavailable. API còn lại (persons, tree) tiếp tục hoạt động.

### 3. Photo URLs: Presigned GETs Chỉ Cho Detail

`photo_url` là **presigned 1h GET link**, chỉ sinh ở:
- `GET /persons/{pid}` (detail)
- `POST /photo-urls` (batch, max 100 ids)

**KHÔNG** trên:
- `/tree` — chỉ `has_photo: bool`
- `/persons` list — chỉ có ở detail

### 4. `force=true` Query Param (Chỉ Owner)

`?force=true` trên `POST /persons` và `PATCH /persons/{pid}` bỏ qua check `parent_born_before_child` (12 năm tối thiểu). Hữu ích khi dữ liệu gia phả không chính xác.

**Chỉ owner được dùng.** Editor dùng → 403.

### 5. Visibility Read-Only Trên PATCH Clan

`visibility` trên `PATCH /clans/{id}` bị bỏ qua (read-only). Duy nhất cách toggle:
- **`POST /clans/{id}/public-link`** → enable, sinh `public_slug` mới
- **`DELETE /clans/{id}/public-link`** → disable, xóa `public_slug`

Cả hai owner-only, atomic: `visibility` và `public_slug` di chuyển cùng nhau. Re-enable lúc nào cũng sinh **slug khác**.

### 6. Ngày Âm Lịch (Lịch Việt)

Giỗ lưu ở 3 field: `death_lunar_day`, `death_lunar_month`, `death_lunar_leap`. Đây là **âm lịch Việt** (UTC+7). Xem `docs/system-architecture.md` → "Lunar Calendar".

- `death_lunar_day`: 1–30
- `death_lunar_month`: 1–12
- `death_lunar_leap`: bool -- **hiện KHÔNG được dùng.** Lưu được nhưng thuật toán tính giị bỏ qua: giị luôn rơi vào tháng thường, kể cả khi người mất ở tháng nhuận. Client gửi `true` sẽ được lưu nhưng không ảnh hưởng kết quả `/lich-gio`.

### 7. Public Endpoint: Không Auth, Chặt Chẽ Chính Sách

`/public/{slug}/tree` và `/public/{slug}/persons/{person_id}` không cần auth. Tất cả response bao gồm:
```
X-Robots-Tag: noindex, nofollow
Cache-Control: no-store
```

**404 nếu:**
- Slug không tồn tại hoặc bị revoke
- Clan private
- Clan soft-deleted

**Người sống (living) bị che:**
- `ho_ten` → viết tắt hoặc placeholder
- `que_quan`, `nghe_nghiep`, `tieu_su` → trống
- `has_photo` → luôn false
- `photo_url` → luôn null

**Tọa độ mộ KHÔNG bao giờ public:** `mo_phan_lat`, `mo_phan_lng`, `mo_phan_note` không trả cho ai.

**Marriage bị bỏ:** Public tree chỉ có parent/child edge; vợ chồng xuất hiện tách rời.

---

## Endpoint Theo Chủ Đề

### Họ: CRUD

| Endpoint | Method | Quyền | Ghi Chú |
|----------|--------|-------|--------|
| `/clans` | GET | `IsAuthenticated` | Họ người dùng thuộc về. Response: `{data: [clan, ...]}` |
| `/clans` | POST | `IsAuthenticated` | Tạo họ. Request: `{ten_ho, thuy_to?, mo_ta?, hide_living_details?}`. Caller → `owner`. Response: `{data: clan}` (201) |
| `/clans/{clan_id}` | GET | `IsClanMember` | Fetch một họ. Non-member → 404. Response: `{data: clan}` |
| `/clans/{clan_id}` | PATCH | `IsClanOwner` | Update từng phần. Writable: `ten_ho`, `thuy_to`, `mo_ta`, `hide_living_details`. `visibility` bỏ qua. Response: `{data: clan}` |
| `/clans/{clan_id}` | DELETE | `IsClanOwner` | Soft-delete. Response: 204 |

**Schema họ:** `id`, `ten_ho`, `thuy_to`, `mo_ta`, `hide_living_details` (bool), `visibility` (read-only: `private` hay `public_link`), `public_slug` (read-only, owner-only trong response), `created_at`, `updated_at`

### Chia Sẻ Công Khai: Toggle

| Endpoint | Method | Quyền | Ghi Chú |
|----------|--------|-------|--------|
| `/clans/{clan_id}/public-link` | POST | `IsClanOwner` | Enable public. Sinh `public_slug` mới. Response: `{data: {slug, url}}` |
| `/clans/{clan_id}/public-link` | DELETE | `IsClanOwner` | Revoke. Xóa `public_slug`. Slug cũ → 404 ngay. Response: 204 |

### Membership & Invite

| Endpoint | Method | Quyền | Ghi Chú |
|----------|--------|-------|--------|
| `/clans/{clan_id}/members` | GET | `IsClanMember` | Danh sách thành viên. Response: `{data: [member, ...]}` |
| `/clans/{clan_id}/members/{user_id}` | PATCH | `IsClanOwner` | Thay role. Request: `{role}` (`owner`/`editor`/`viewer`). Không demote owner cuối cùng. Response: `{data: member}` |
| `/clans/{clan_id}/members/{user_id}` | DELETE | `IsClanOwner` | Xóa thành viên. Không xóa owner cuối cùng. Response: 204 |
| `/clans/{clan_id}/invites` | GET | `IsClanOwner` | Danh sách tất cả invite (đã dùng + chưa). Response: `{data: [invite, ...]}` |
| `/clans/{clan_id}/invites` | POST | `IsClanOwner` | Tạo code mời. Request: `{role?, expires_at?, max_uses?}`. Default: `role='viewer'`, `expires_at=now+30d`, `max_uses=0`. Response: `{data: invite}` (201) |
| `/clans/{clan_id}/invites/{invite_id}` | DELETE | `IsClanOwner` | Revoke code. Response: 204 |
| `/join` | POST | `IsAuthenticated` | Dùng code mời. Request: `{code}`. Idempotent. Throttle: 10/h. Response: `{data: member}` (200) |

**Member schema:** `user_id`, `display_name`, `role`, `joined_at`; thêm `username` và `email` **chỉ khi caller là owner**
(xem mục "Thay Đổi Không Tương Thích" ở trên). `display_name` = `first_name last_name`; tài khoản chưa đặt tên → 3 ký tự
đầu của phần trước `@` + `***` (ví dụ `ngu***`).

**Invite schema:** `id`, `code`, `role` (`editor` hay `viewer`, không `owner`), `expires_at`, `max_uses`, `used_count`, `created_at`

### Person: CRUD + Tìm Kiếm

| Endpoint | Method | Quyền | Query Param | Ghi Chú |
|----------|--------|-------|---|--------|
| `/clans/{clan_id}/persons` | GET | `IsClanMember` | `q`, `generation`, `branch`, `death_year`, `limit`, `offset` | Paginated, search/filter. Default limit 50, max 200. Response: `{data: [...], count, next, previous}` |
| `/clans/{clan_id}/persons` | POST | `IsClanEditor` | `force` | Bulk: single object hoặc array (max 200). Response: `{data: person}` hoặc `{data: [...]}` (201) |
| `/clans/{clan_id}/persons/{person_id}` | GET | `IsClanMember` | — | Response: `{data: person}` với `photo_url` (presigned 1h nếu có ảnh) |
| `/clans/{clan_id}/persons/{person_id}` | PATCH | `IsClanEditor` | `force` | Request: subset writable field. Response: `{data: person}` |
| `/clans/{clan_id}/persons/{person_id}` | DELETE | `IsClanEditor` | — | Soft-delete. Fail 400 nếu có con tham chiếu. Response: 204 |

**Person write field:** `ho_ten` và `gioi_tinh` (required), `ten_huy`, `ten_tu`, `ten_hieu`, `thuy_hieu`, `gioi_tinh` (`nam`/`nu`/`khac`), `father_id`, `mother_id`, `parent_kind` (`ruot`/`nuoi`/`ke`), `branch`, `birth_order`, `is_truong`, `birth_solar`, `birth_lunar_day`, `birth_lunar_month`, `birth_lunar_leap`, `death_solar`, `death_lunar_day`, `death_lunar_month`, `death_lunar_leap`, `que_quan`, `nghe_nghiep`, `tieu_su`, `mo_phan_lat`, `mo_phan_lng`, `mo_phan_note`

**Person read field:** Trên + `id`, `generation` (derived), `father_name`, `mother_name`, `photo_url` (detail only), `is_deleted`, `created_at`, `updated_at`

### Revisions: Lịch Sử & Restore

| Endpoint | Method | Quyền | Ghi Chú |
|----------|--------|-------|--------|
| `/clans/{clan_id}/persons/{person_id}/revisions` | GET | `IsClanEditor` | Lịch thay đổi, newest first, paginated (`limit` mặc định 50, max 200). Vẫn đọc được với người đã xoá mềm. Response: `{data: [...], count, next, previous}` |
| `/clans/{clan_id}/persons/{person_id}/restore/{revision_id}` | POST | `IsClanEditor` | Re-apply snapshot. Validate theo tree rules (không có `force`). Trạng thái trước restore được ghi thành revision mới. Response: `{data: person}` — **`photo_url` luôn `null`** ở response này (không phải detail) |

**Revision schema:** `id`, `action` (`create`/`update`/`delete`), `actor_username`, `payload_json`, `created_at`

**`payload_json` KHÔNG chứa 6 field** (`services/revision.py::_EXCLUDED_FIELDS`): `id`, `created_at`, `updated_at`, `is_deleted`, `clan_id`, `photo_key`.

Quan trọng cho client: **restore KHÔNG khôi phục ảnh và KHÔNG undelete.** Ảnh và soft-delete là hành động riêng, không phải nội dung gia phả — restore chỉ trả lại nội dung. Muốn đổi ảnh thì đi luồng 3 bước ở mục 2; muốn khôi phục người đã xoá mềm thì **API không có endpoint nào làm được** — chỉ sửa trực tiếp trong Django admin.

Bộ lọc này áp dụng cả khi ĐỌC payload, không chỉ khi ghi — nên revision cũ (tạo trước bản vá) vẫn không restore được `photo_key` dù trong DB payload của nó còn field đó.

### Marriage

| Endpoint | Method | Quyền | Ghi Chú |
|----------|--------|-------|--------|
| `/clans/{clan_id}/marriages` | GET | `IsClanMember` | List marriages. Response: `{data: [marriage, ...]}` |
| `/clans/{clan_id}/marriages` | POST | `IsClanEditor` | Request: `{husband_id, wife_id, status, order?, note?}`. Default: `order=max+1`. Both must be in clan. Response: `{data: marriage}` (201) |
| `/clans/{clan_id}/marriages/{marriage_id}` | PATCH | `IsClanEditor` | Update `order`, `status`, `note`. Cannot change `husband_id`/`wife_id`. Response: `{data: marriage}` |
| `/clans/{clan_id}/marriages/{marriage_id}` | DELETE | `IsClanEditor` | Response: 204 |

**Marriage schema:** `id`, `husband_id`, `husband_name`, `wife_id`, `wife_name`, `order` (1=vợ cả), `status` (`dang_ket_hon`/`ly_hon`/`goa`), `note`

### Cây (Tree)

| Endpoint | Method | Quyền | Query Param | Ghi Chú |
|----------|--------|-------|---|--------|
| `/clans/{clan_id}/tree` | GET | `IsClanMember` | `root`, `depth` | Flat nodes + edges. Subtree filter in-memory. Response: `{clan, nodes, edges, truncated}` (no `data` envelope). Query budget: 3. |

**Response:** `clan {id, ten_ho}`, `nodes` array, `edges` array (parent/marriage), `truncated` (bool — true khi họ vượt `MAX_CLAN_PERSONS` = 5000 và phần đuôi bị cắt)

- **Node:** `id`, `ho_ten`, `ten_huy`, `gioi_tinh`, `generation`, `branch`, `is_truong`, `birth_order`, `is_living`, `birth_year`, `death_year`, `death_lunar`, `has_photo`. Không có `photo_url`.
- **Edge parent:** `{type: "parent", from, to, role, kind}` (`kind` = `parent_kind`).
- **Edge marriage:** `{type: "marriage", a, b, order, status}`.
- `root` không thuộc họ → 404. `root`/`depth` phải là số nguyên dương, sai → 400.

### Ảnh: Upload & URLs

| Endpoint | Method | Quyền | Ghi Chú |
|----------|--------|-------|--------|
| `/clans/{clan_id}/persons/{person_id}/photo-upload-url` | POST | `IsClanEditor` | Request: `{content_type, size}`. Response: `{data: {upload_url, key, expires_in: 300}}`. Xem #2 trên. |
| `/clans/{clan_id}/persons/{person_id}/photo` | POST | `IsClanEditor` | Confirm uploaded. Request: `{key}`. Validate shape, HEAD, enforce 5MB. Response: `{data: person}` |
| `/clans/{clan_id}/persons/{person_id}/photo` | DELETE | `IsClanEditor` | Remove photo. Response: 204 |
| `/clans/{clan_id}/photo-urls` | POST | `IsClanMember` | Batch presigned GETs. Request: `{person_ids: [...]}` (max 100). Response: `{data: {person_id: url, ...}}` |

### Tệp: Upload Dùng Chung (`apis/`)

| Endpoint | Method | Quyền | Ghi Chú |
|----------|--------|-------|--------|
| `/api/files/upload-url` | POST | `AllowAny` + throttle | Request: `{content_type, size}`. Response: `{data: {upload_url, key, expires_in: 300}}`. Key: `uploads/{32 hex}.{jpg\|png\|webp}` |
| `/api/files/confirm` | POST | `AllowAny` + throttle | Request: `{key}`. Validate shape, HEAD, enforce 5MB + content-type thật. Response: `{data: {key, url, expires_in: 3600}}` |

Không ghi DB (query budget: 0). Xem mục "Tải Tệp Lên" trên để biết giới hạn và rủi ro
`AllowAny`.

### Lịch Giỗ

| Endpoint | Method | Quyền | Query Param | Ghi Chú |
|----------|--------|-------|---|---------|
| `/clans/{clan_id}/lich-gio` | GET | `IsClanMember` | `from`, `to`, `year` | Window → lunar giỗ. Response: `{items, truncated}` (no `data` envelope). Query budget: 2. |

**Query param:** `year=YYYY` hoặc `from=YYYY-MM-DD` + `to=YYYY-MM-DD` hoặc omit all (next 12 months). Max window 731 days, year 1–9999.

**Item:** `person_id`, `ho_ten`, `thuy_hieu`, `generation`, `lunar {day, month}`, `lunar_year`, `solar_date`, `can_chi_ngay`, `days_until`, `adjusted` (bool: day-30 → day-29?)

### Giỗ Follower & Device

| Endpoint | Method | Quyền | Ghi Chú |
|----------|--------|-------|--------|
| `/clans/{clan_id}/toi-la` | GET | `IsClanMember` | "Tôi là ai?" — binding node người dùng. Response: `{data: {person_id, ho_ten}}` hoặc `{data: null}` |
| `/clans/{clan_id}/toi-la` | PUT | `IsClanMember` | Request: `{person_id}`. Bind caller. Reject deceased/khác họ/claimed by another. Response: `{data: binding}` |
| `/clans/{clan_id}/toi-la` | DELETE | `IsClanMember` | Unbind. Response: 204 |
| `/clans/{clan_id}/gio-follows` | GET | `IsClanMember` | Resolved follow list. Response: `{items, bound, truncated}` (no `data` envelope). Query budget **5, cố định** — ghim bằng `assertNumQueries` trong `test_gio_follow_api.py`, không nằm trong snapshot `query_budgets.json` (snapshot đó chỉ có 7 endpoint). |
| `/clans/{clan_id}/gio-follows/{person_id}` | PUT | `IsClanMember` | Request: `{enabled: bool}`. Person must have lunar death date or 400. Response: `{data: {person_id, enabled}}` |
| `/clans/{clan_id}/gio-follows/{person_id}` | DELETE | `IsClanMember` | Remove override. Idempotent. Response: 204 |
| `/devices` | POST | `IsAuthenticated` (not clan-scoped) | Register device. Request: `{token, platform}`. Upsert on token (takeover nếu re-register). Response: `{data: {platform, is_active}}` (201 new / 200 existing). **Token never returned.** |
| `/devices` | DELETE | `IsAuthenticated` (not clan-scoped) | Logout device. Request: `{token}`. Idempotent. Response: 204. **Token never logged.** |

**Device platform:** `ios`, `android`, `web`

**GioFollow item:** `person_id`, `ho_ten`, `thuy_hieu`, `generation`, `lunar {day, month}`, `followed`, `source` (`truc-he`/`thu-cong`/`da-bo`)

### Xưng Hô

| Endpoint | Method | Quyền | Query Param | Ghi Chú |
|----------|--------|-------|---|--------|
| `/clans/{clan_id}/xung-ho` | GET | `IsClanMember` | `a`, `b` | Xưng hô Việt. `a` default binding caller (chưa bind → 400). `b` required. `a`/`b` không thuộc họ → 400. Response: `{a_calls_b, b_calls_a, common_ancestor, path, explain}` (no `data` envelope). Query budget: **2** khi truyền `a` và có huyết thống; +1 nếu bỏ `a` (tra binding); +1 nếu không cùng huyết thống (tra hôn nhân); **tối đa 4**. Snapshot `query_budgets.json` ghi 3 (test bỏ `a`) — vượt target 2 trong plan. |

**Response:** `a_calls_b {term, confident, reason}`, `b_calls_a` (same), `common_ancestor {id, ho_ten}` (null on in-law), `path {a_up, b_up, side}` (always object, fields null on in-law; `side` = `noi`/`ngoai`), `explain` (prose)

**No blood link = 200 với `term: null`, không error.**

`reason` là slug ASCII để client rẽ nhánh, không hiển thị: `khong_cung_huyet_thong`, `cung_mot_nguoi`,
`thieu_birth_order`, `thieu_gioi_tinh`, `khong_co_tu_xung_ho_thong_dung`, `nhieu_hon_nhan_ngang_hang`,
`ngoai_bang_tu_vung`. Chữ tiếng Việt tương ứng nằm trong `explain`.

### Public Page (Không Auth)

| Endpoint | Method | Quyền | Ghi Chú |
|----------|--------|-------|--------|
| `/public/{slug}/tree` | GET | None (`AllowAny`) | Public tree. 404 nếu slug invalid/revoke/private. Redact living. Throttle: 60/h. Header: `X-Robots-Tag: noindex, nofollow`, `Cache-Control: no-store`. Response: `{clan, nodes, edges, truncated}` (no `data` envelope). Query budget **4** (clan lookup + quét sống/mất + 1 query mỗi nhánh) — vượt target 3; đây là giá phải trả của việc tách field list theo nhánh sống/mất. |
| `/public/{slug}/persons/{person_id}` | GET | None (`AllowAny`) | Person detail. 404 nếu not found/slug invalid. Redact living. Response: `{data: person}` |

Chỉ nhận `GET`/`HEAD` (kể cả `OPTIONS` → 405) và chỉ render JSON (`Accept: text/html` không mở browsable API).

- **Public tree node:** `id`, `ho_ten`, `ten_huy`, `generation`, `branch`, `is_truong`, `birth_order`, `is_living`, `birth_year`, `death_year`, `death_lunar`, `has_photo`. Không có `gioi_tinh`.
- **Public tree edge:** chỉ `{type: "parent", from, to, role}` — không có `kind` (không lộ con nuôi/con kế), không có edge marriage.
- **Public person:** node + `ten_tu`, `ten_hieu`, `thuy_hieu`, `que_quan`, `nghe_nghiep`, `tieu_su`, `photo_url` (presigned 1h, chỉ người đã mất).

---

## Gia Phả Cá Nhân (`/api/gia-pha/v1/family/`)

**Mục đích:** Cây phả hệ riêng của mỗi người dùng (một user = một gia phả). Không dùng chung với cây cộng tộc (clan); mỗi người dùng quản lý gia phả cá nhân độc lập.

**Xác thực:** Tất cả endpoint cần token JWT bearer. Family tự động tạo lần đầu tiên khi user truy cập.

**Hợp đồng API:** `docs/gia-pha-api-spec.md`, `docs/gia-pha-architecture.md`

### Danh Sách Endpoint

| Method | Path | Chức năng | Body |
|--------|------|----------|------|
| `GET` | `/v1/family` | Lấy toàn bộ cây + `selfId` | — |
| `GET` | `/v1/family/persons/{id}` | Chi tiết một người | — |
| `POST` | `/v1/family/persons` | Tạo người mới; tự nối theo `relationship` nếu có | `PersonDraft` |
| `PATCH` | `/v1/family/persons/{id}` | Sửa thông tin (không cạnh quan hệ) | `PersonDraft` |
| `DELETE` | `/v1/family/persons/{id}` | Xoá người, gỡ cạnh trỏ đến họ | — |
| `PUT` | `/v1/family/self` | Đặt "Đây là tôi" | `{personId: uuid \| null}` |
| `PUT` | `/v1/family/persons/{id}/gio-event` | Gắn/gỡ sự kiện giỗ | `{eventId: uuid \| null}` |
| `POST` | `/v1/family/relations/add-relative` | Tạo người mới + nối 1 cạnh (`father`, `mother`, `spouse`, `child`, `sibling`) | `{anchorId, kind, person, otherParentId?}` |
| `POST` | `/v1/family/relations/set-parent` | Đặt/xoá cha hoặc mẹ | `{childId, slot, parentId, rel?}` |
| `POST` | `/v1/family/relations/link-spouse` | Nối vợ/chồng (2 chiều) | `{aId, bId, type?}` |
| `POST` | `/v1/family/relations/unlink-spouse` | Gỡ vợ/chồng (2 chiều) | `{aId, bId}` |
| `POST` | `/v1/family/relations/link-child` | Nối người đã có làm con | `{parentId, childId, otherParentId?}` |

### Person JSON

Tất cả response chứa mảng `persons[]` với structure sau (camelCase):

```json
{
  "id": "uuid",
  "name": "Nguyễn Văn A",
  "gender": "male" | "female" | "unknown",
  "deceased": false,
  "fatherId": "uuid" | null,
  "motherId": "uuid" | null,
  "fatherRel": "blood" | "adopted" | null,
  "motherRel": "blood" | "adopted" | null,
  "spouses": [{"id": "uuid", "type": "married" | "divorced"}, ...],
  "solarBirthDate": "DD-MM-YYYY" | null,
  "birthTime": "HH:mm" | null,
  "birthOrder": 1 | null,
  "solarDeathDate": "DD-MM-YYYY" | null,
  "deathTime": "HH:mm" | null,
  "lunarDeathDay": 1–30 | null,
  "lunarDeathMonth": 1–12 | null,
  "lunarDeathYear": 1900–2100 | null,
  "lunarLeap": true | false | null,
  "relationship": "Cha" | "Mẹ" | "Vợ" | ... | null,
  "note": "ghi chú tự do" | null,
  "gioEventId": "event-id" | null,
  "createdAt": 1726074000000,
  "updatedAt": 1726074000000
}
```

**Ghi chú:**
- `createdAt`, `updatedAt` là **epoch milliseconds** (tính từ 1970-01-01 UTC).
- `solarBirthDate`, `solarDeathDate`: định dạng `"DD-MM-YYYY"` (zero-pad, vd `"01-01-1990"`).
- `birthTime`, `deathTime`: định dạng `"HH:mm"` 24h (vd `"14:30"`).
- `solarDeathDate` suy ra từ `lunarDeathDay/Month/Year` khi đủ dữ liệu.
- `fatherRel` / `motherRel`: chỉ ghi `"adopted"` khi nuôi; mặc định `"blood"` (lưu `null`).
- `spouses`: luôn là mảng, có thể rỗng `[]`.
- PATCH **không đổi** `fatherId`, `motherId`, `spouses` — dùng `/relations/*` để thay đổi cạnh.

### Response Thành Công (Đọc)

```json
{
  "selfId": "uuid" | null,
  "persons": [{ ...person }, ...]
}
```

`GET /v1/family` trả cả cây. `GET /persons/{id}` trả chi tiết người đó (tùy chọn; client có thể dẫn xuất từ cây).

### Response Thành Công (Tạo/Sửa/Xoá)

```json
{
  "ok": true,
  "person": { ...person },
  "persons": [{ ...person }, ...],
  "warning": null | { "code": "SPOUSE_IS_ANCESTOR", "personId": "uuid", "otherId": "uuid", "message": "..." }
}
```

- `person`: người vừa tạo/sửa/tham gia mutation.
- `persons`: danh sách **sau** mutation (cây nhỏ, 2 query).
- `warning`: `null` hoặc `{code, personId, otherId, message}`. Hai warning: `SPOUSE_IS_ANCESTOR` (link-spouse: hai người trực hệ, vẫn lưu) và `OTHER_PARENT_NOT_CANDIDATE` (link-child / add-relative kind=child: `otherParentId` không thuộc partners hợp lệ → ô còn lại để trống).

### Response Thành Công (Xoá)

```json
{
  "deleted": true,
  "detachedFrom": ["uuid", ...],
  "selfId": "uuid" | null
}
```

- `detachedFrom`: danh sách người bị gỡ cạnh (cha/mẹ trỏ người bị xoá).
- `selfId`: mới (nếu người xoá là `selfId`, nó trở `null`).

### Response Lỗi

Tất cả lỗi trả **400** (trừ `PERSON_NOT_FOUND` → **404**):

```json
{
  "ok": false,
  "error": {
    "code": "SELF_PARENT" | "PARENT_CYCLE" | "PARENT_SLOT_TAKEN" | ... ,
    "personId": "uuid" | null,
    "otherId": "uuid" | null,
    "message": "Không đặt được: người này đang là con cháu...",
    "fields": { "name": ["error"], ... } | null
  }
}
```

**Mã lỗi (code):**

| Code | Ý nghĩa | HTTP |
|------|---------|------|
| `SELF_PARENT` | A là cha/mẹ của chính A | 400 |
| `SELF_SPOUSE` | A nối vợ/chồng với chính A | 400 |
| `PARENT_CYCLE` | Sắp làm cha/mẹ nhưng đang là con cháu → vòng lặp | 400 |
| `PARENT_SLOT_TAKEN` | Ô cha/mẹ đã có người khác | 400 |
| `DANGLING_FATHER` / `DANGLING_MOTHER` / `DANGLING_SPOUSE` | ID trỏ người không tồn tại | 400 |
| `SPOUSE_IS_ANCESTOR` | Hai người đang trực hệ (warning chỉ, vẫn lưu) | 200 |
| `OTHER_PARENT_NOT_CANDIDATE` | `otherParentId` không phải vợ/chồng hay đồng phụ huynh hợp lệ (warning, ô để trống) | 200 |
| `FAMILY_FULL` | Gia phả đạt giới hạn `FAMILY_MAX_PERSONS` (mặc định 1000, `settings.py`) | 400 |
| `GENDER_MISMATCH` | Giới tính không hợp ô (nam ≠ mẹ, nữ ≠ cha) | 400 |
| `NO_PARENT_FOR_SIBLING` | Thêm anh chị em khi chưa có cha **và** mẹ | 400 |
| `SELF_ALREADY_SET` | Đã có "tôi", gỡ cái cũ trước khi đổi | 400 |
| `PERSON_NOT_FOUND` | Người không tồn tại | 404 |
| `VALIDATION` | Dữ liệu không hợp lệ (tên rỗng, ngày sai, ...) | 400 |

**Đối với validation error (4xx với `code = "VALIDATION"`):** `fields` dict chứa lỗi từng trường (DRF format).

### Ví Dụ: Thêm Anh Chị Em

```bash
POST /api/gia-pha/v1/family/relations/add-relative
Authorization: Bearer {token}
Content-Type: application/json

{
  "anchorId": "123e4567-e89b-12d3-a456-426614174000",
  "kind": "sibling",
  "person": {
    "name": "Nguyễn Văn B",
    "gender": "male",
    "relationship": "Em"
  }
}
```

**Response 200:**
```json
{
  "ok": true,
  "person": {
    "id": "223e4567-e89b-12d3-a456-426614174001",
    "name": "Nguyễn Văn B",
    "gender": "male",
    "deceased": false,
    "fatherId": "uuid-of-father",
    "motherId": "uuid-of-mother",
    "spouses": [],
    "relationship": "Em",
    "createdAt": 1726074123000,
    "updatedAt": 1726074123000,
    ...
  },
  "persons": [
    {...anchor with updated data...},
    {...person vừa tạo...},
    ...other persons...
  ],
  "warning": null
}
```

### Ví Dụ: Nối Vợ/Chồng Lần Đầu Tiên (Auto-fill cha/mẹ con)

Khi nối vợ/chồng đầu tiên của người có sẵn con chưa có mẹ (hoặc cha), server tự điền ô trống:

```bash
POST /api/gia-pha/v1/family/relations/link-spouse
{
  "aId": "dad-uuid",
  "bId": "mom-uuid",
  "type": "married"
}
```

**Result:** Con chưa có mẹ tự động lấy `motherId = mom-uuid` (nếu giới tính hợp).

### Ví Dụ: Lỗi Vòng Lặp

```bash
POST /api/gia-pha/v1/family/relations/set-parent
{
  "childId": "ông-uuid",
  "slot": "father",
  "parentId": "cháu-uuid"
}
```

**Response 400:**
```json
{
  "ok": false,
  "error": {
    "code": "PARENT_CYCLE",
    "personId": "ông-uuid",
    "otherId": "cháu-uuid",
    "message": "Không đặt được: người này đang là con cháu trong nhánh đó, nối vào sẽ tạo vòng lặp."
  }
}
```

### Ví Dụ: Lỗi Validation

```bash
POST /api/gia-pha/v1/family/persons
{
  "name": "",
  "gender": "invalid_gender"
}
```

**Response 400:**
```json
{
  "ok": false,
  "error": {
    "code": "VALIDATION",
    "message": "Tên là bắt buộc.",
    "fields": {
      "name": ["This field may not be blank."],
      "gender": ["Invalid choice."]
    }
  }
}
```

---

## Response Lỗi

Tất cả lỗi except 204 có body.

### 400 Bad Request

Hai dạng, client phải xử lý cả hai:

```json
{"field_name": ["Error message", ...]}
```
Lỗi validate body (serializer), khoá là tên trường.

```json
{"detail": "Tham số year phải là số nguyên."}
```
Lỗi nghiệp vụ hoặc query param sai (`BadRequestException`): sai cửa sổ `lich-gio`, `person_id` khác họ,
key ảnh sai hình dạng, xoá người còn con, v.v. Ở `apis/` lỗi query param có dạng
`Tham số 'x' không hợp lệ: <lý do>`.

### 403 Forbidden
```json
{"detail": "Localized permission message"}
```

### 404 Not Found
```json
{"detail": "Không tìm thấy..."}
```

### 405 Method Not Allowed
Public endpoint với method khác `GET`/`HEAD`.

### 429 Too Many Requests
Throttled — xem retry-after header.

### 503 Service Unavailable
Ba endpoint ảnh gia phả và cả hai endpoint `/api/files` — khi `S3_*` chưa cấu hình. Phần API
còn lại không ảnh hưởng.

---

## Trạng Thái Nghiệm Thu

- **`/api/files` — ĐÃ chạy end-to-end với bucket thật (2026-09-09).** `calendar-giapha-prod`,
  `ap-northeast-1`: mint → `PUT` một PNG thật thẳng lên S3 (200) → `confirm` (200) →
  presigned `GET` (200), byte nhận về khớp byte gửi đi. Object test đã xoá sau đó.
- **Ảnh gia phả (`photo-upload-url` / `photo` / `photo-urls`) — 3 view này CHƯA chạy với
  bucket thật.** Lớp storage bên dưới thì đã: `apis/services/storage.py` và
  `giapha/services/storage.py` presign giống hệt nhau, nên signature version, endpoint/region,
  credential và bucket policy tính là đã nghiệm thu qua mục trên. Chưa có bằng chứng: bản thân
  3 view ảnh, và **dọn object mồ côi** (vẫn không có job nào — đặt lifecycle rule trên bucket).
- Hai lỗi từng làm hỏng toàn bộ luồng upload (sai signature version, sai region/endpoint) chỉ
  bị phát hiện bằng tay trên máy production, không phải bởi test — mock `boto3` nhận mọi kwarg
  mà không phàn nàn. `StorageClientConstructionTests` giờ ghim cả hai.
- **Push nhắc giỗ / nhắc lịch hẹn / FCM:** `POST /devices` nhận và lưu token bình thường, nhưng **chưa có push nào tới máy thật**. Toàn bộ đường FCM (cả `remind_death_anniversary` lẫn `remind_appointment_date`) chỉ nghiệm thu qua mock. Client đăng ký token thành công KHÔNG có nghĩa là sẽ nhận được thông báo.

---

## Tài Liệu Liên Quan

- **Lunar Calendar**: `docs/system-architecture.md` → "Lunar Calendar"
- **System Architecture**: `docs/system-architecture.md`
- **Code Standards**: `docs/code-standards.md`
- **Codebase Overview**: `docs/codebase-summary.md`
