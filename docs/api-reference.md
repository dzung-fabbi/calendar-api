# Tài Liệu API giapha

Đường dẫn gốc: `/api/gia-pha/`

## Xác Thực

Tất cả endpoint cần token OAuth2 bearer (trừ public endpoint ghi chú riêng):
```
Authorization: Bearer {access_token}
```

Endpoint auth (từ `djangopj/auth_token_views.py` trên `django-oauth-toolkit`, mount ở `/auth/` — dấu `/` cuối là tuỳ chọn):

| Endpoint | Dùng khi |
|---|---|
| `POST /auth/token` | Lấy token bằng username/password (grant `password`) hoặc làm mới token (grant `refresh_token`) |
| `POST /auth/revoke-token` | Thu hồi token (logout) |

**Ghi chú:**
- Cả hai endpoint chấp nhận body dạng `application/x-www-form-urlencoded` hoặc JSON (`application/json`).
- Endpoint sau đây **đã bị xóa** và trả về 404: `/auth/convert-token`, `/auth/login/{provider}/`, `/auth/authorize`, `/auth/invalidate-sessions`, `/auth/invalidate-refresh-tokens`, `/auth/disconnect-backend`. **Đăng nhập Facebook/Google không còn được hỗ trợ.**

### Bao Đóng Response

Hầu hết endpoint trả về response bao trong `{"data": ...}`. **Ngoại lệ:**
- **204 No Content** (DELETE) không có body
- Validation errors (400) trả dict lỗi trực tiếp, không bao
- Public endpoint `/public/{slug}/tree` và `/public/{slug}/persons/{person_id}` trả serializer data không bao

## ⚠️ Thay Đổi Không Tương Thích: Danh Sách Thành Viên Họ

`GET /api/gia-pha/clans/{id}/members` (và các response chứa `ClanMember`) **không còn trả
`username`** cho `editor`/`viewer` — chỉ `owner` mới thấy. Thay vào đó có trường mới
**`display_name`** (họ + tên; nếu tài khoản chưa đặt tên thì là dạng che `ngu***`).

**Lý do:** đăng ký tài khoản lưu email làm `username`. Serializer vốn đã cố ý giấu `email`
với người không phải chủ họ, nhưng vẫn trả `username` — nên nếu giữ nguyên, một `viewer` vào
họ bằng invite code sẽ lấy được đúng danh sách email mà cái khoá kia sinh ra để bảo vệ.

**Client cần làm:** đổi chỗ hiển thị `username` sang `display_name`.

## Tài Khoản (`/api/`)

Các endpoint quản lý tài khoản nằm ở app `apis/`, **không** phải `/api/gia-pha/`. Ghi ở đây
vì chúng bổ sung cho phần "Xác Thực" bên trên: `/auth/token` cấp token, nhóm này lo phần
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
  chữ thường. Đăng ký xong dùng ngay `/auth/token` với `grant_type=password`, không có bước
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
- Tài khoản Facebook/Google cũ (không có mật khẩu dùng được) **đặt lại được** qua luồng này.

### Đổi mật khẩu và thu hồi token

**`reset-password` và `change-password` đều xoá TOÀN BỘ access + refresh token của tài
khoản** — kể cả token đang gọi chính request đó. Sau khi nhận 200, client **phải đăng nhập
lại**; token cũ sẽ trả 401 ở request kế tiếp. Đây là hành vi cố ý: đổi mật khẩu vì bị lộ thì
phải đẩy được kẻ đang giữ token ra ngoài.

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

## Mô Hình Phân Quyền

**Ba vai trò:** `owner` (quản trị họ), `editor` (viết person/marriage), `viewer` (chỉ đọc).

**Quan trọng:** Người ngoài họ nhận **404 Not Found**, không bao giờ 403 Forbidden. 403 sẽ xác nhận họ tồn tại.

**Chuyển ownership chỉ qua admin** — invite code cấp tối đa `editor`/`viewer`, không bao giờ `owner`.

## Throttle (Giới Hạn Tần Suất)

- **`POST /join`** (`giapha-join` scope): 10 yêu cầu/giờ mỗi IP
- **Public tree/person endpoints** (`giapha-public` scope): 60 yêu cầu/giờ mỗi IP
- Endpoint khác: không giới hạn

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

**Member schema (owner thấy email, khác thấy username):** `user_id`, `username`, `email` (owner-only), `role`, `joined_at`

**Invite schema:** `id`, `code`, `role` (`editor` hay `viewer`, không `owner`), `expires_at`, `max_uses`, `used_count`, `created_at`

### Person: CRUD + Tìm Kiếm

| Endpoint | Method | Quyền | Query Param | Ghi Chú |
|----------|--------|-------|---|--------|
| `/clans/{clan_id}/persons` | GET | `IsClanMember` | `q`, `generation`, `branch`, `death_year`, `limit`, `offset` | Paginated, search/filter. Default limit 50, max 200. Response: `{data: [...], count, next, previous}` |
| `/clans/{clan_id}/persons` | POST | `IsClanEditor` | `force` | Bulk: single object hoặc array (max 200). Response: `{data: person}` hoặc `{data: [...]}` (201) |
| `/clans/{clan_id}/persons/{person_id}` | GET | `IsClanMember` | — | Response: `{data: person}` với `photo_url` (presigned 1h nếu có ảnh) |
| `/clans/{clan_id}/persons/{person_id}` | PATCH | `IsClanEditor` | `force` | Request: subset writable field. Response: `{data: person}` |
| `/clans/{clan_id}/persons/{person_id}` | DELETE | `IsClanEditor` | — | Soft-delete. Fail 400 nếu có con tham chiếu. Response: 204 |

**Person write field:** `ho_ten` (required), `ten_huy`, `ten_tu`, `ten_hieu`, `thuy_hieu`, `gioi_tinh` (`nam`/`nu`/`khac`), `father_id`, `mother_id`, `parent_kind` (`ruot`/`nuoi`/`ke`), `branch`, `birth_order`, `is_truong`, `birth_solar`, `birth_lunar_day`, `birth_lunar_month`, `birth_lunar_leap`, `death_solar`, `death_lunar_day`, `death_lunar_month`, `death_lunar_leap`, `que_quan`, `nghe_nghiep`, `tieu_su`, `mo_phan_lat`, `mo_phan_lng`, `mo_phan_note`

**Person read field:** Trên + `id`, `generation` (derived), `father_name`, `mother_name`, `photo_url` (detail only), `is_deleted`, `created_at`, `updated_at`

### Revisions: Lịch Sử & Restore

| Endpoint | Method | Quyền | Ghi Chú |
|----------|--------|-------|--------|
| `/clans/{clan_id}/persons/{person_id}/revisions` | GET | `IsClanEditor` | Lịch thay đổi, newest first, paginated. Response: `{data: [...], count, next, previous}` |
| `/clans/{clan_id}/persons/{person_id}/restore/{revision_id}` | POST | `IsClanEditor` | Re-apply snapshot. Validate theo tree rules. Record restore as new revision. Response: `{data: person}` |

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

**Response:** `clan {id, ten_ho}`, `nodes` array, `edges` array (parent/marriage), `truncated` (bool)

### Ảnh: Upload & URLs

| Endpoint | Method | Quyền | Ghi Chú |
|----------|--------|-------|--------|
| `/clans/{clan_id}/persons/{person_id}/photo-upload-url` | POST | `IsClanEditor` | Request: `{content_type, size}`. Response: `{data: {upload_url, key, expires_in: 300}}`. Xem #2 trên. |
| `/clans/{clan_id}/persons/{person_id}/photo` | POST | `IsClanEditor` | Confirm uploaded. Request: `{key}`. Validate shape, HEAD, enforce 5MB. Response: `{data: person}` |
| `/clans/{clan_id}/persons/{person_id}/photo` | DELETE | `IsClanEditor` | Remove photo. Response: 204 |
| `/clans/{clan_id}/photo-urls` | POST | `IsClanMember` | Batch presigned GETs. Request: `{person_ids: [...]}` (max 100). Response: `{data: {person_id: url, ...}}` |

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
| `/clans/{clan_id}/gio-follows` | GET | `IsClanMember` | Resolved follow list. Response: `{items, bound, truncated}` (no `data` envelope). Query budget ~5 — **chưa** được ghim bằng ratchet test, khác 7 endpoint trong `query_budgets.json`. |
| `/clans/{clan_id}/gio-follows/{person_id}` | PUT | `IsClanMember` | Request: `{enabled: bool}`. Person must have lunar death date or 400. Response: `{data: {person_id, enabled}}` |
| `/clans/{clan_id}/gio-follows/{person_id}` | DELETE | `IsClanMember` | Remove override. Idempotent. Response: 204 |
| `/devices` | POST | `IsAuthenticated` (not clan-scoped) | Register device. Request: `{token, platform}`. Upsert on token (takeover nếu re-register). Response: `{data: {platform, is_active}}` (201 new / 200 existing). **Token never returned.** |
| `/devices` | DELETE | `IsAuthenticated` (not clan-scoped) | Logout device. Request: `{token}`. Idempotent. Response: 204. **Token never logged.** |

**Device platform:** `ios`, `android`, `web`

**GioFollow item:** `person_id`, `ho_ten`, `thuy_hieu`, `generation`, `lunar {day, month}`, `followed`, `source` (`truc-he`/`thu-cong`/`da-bo`)

### Xưng Hô

| Endpoint | Method | Quyền | Query Param | Ghi Chú |
|----------|--------|-------|---|--------|
| `/clans/{clan_id}/xung-ho` | GET | `IsClanMember` | `a`, `b` | Xưng hô Việt. `a` default binding caller. `b` required. Response: `{a_calls_b, b_calls_a, common_ancestor, path, explain}` (no `data` envelope). Query budget **3** (4 khi đường quan hệ đi qua dâu/rể) — vượt target 2 trong plan, xem `docs/codebase-summary.md`. |

**Response:** `a_calls_b {term, confident, reason}`, `b_calls_a` (same), `common_ancestor {id, ho_ten}` (null on in-law), `path {a_up, b_up, side}` (always object, fields null on in-law), `explain` (prose)

**No blood link = 200 với `term: null`, không error.**

### Public Page (Không Auth)

| Endpoint | Method | Quyền | Ghi Chú |
|----------|--------|-------|--------|
| `/public/{slug}/tree` | GET | None (`AllowAny`) | Public tree. 404 nếu slug invalid/revoke/private. Redact living. Throttle: 60/h. Header: `X-Robots-Tag: noindex, nofollow`, `Cache-Control: no-store`. Response: `{clan, nodes, edges, truncated}` (no `data` envelope). Query budget **4** (clan lookup + quét sống/mất + 1 query mỗi nhánh) — vượt target 3; đây là giá phải trả của việc tách field list theo nhánh sống/mất. |
| `/public/{slug}/persons/{person_id}` | GET | None (`AllowAny`) | Person detail. 404 nếu not found/slug invalid. Redact living. Response: `{data: person}` |

---

## Response Lỗi

Tất cả lỗi except 204 có body.

### 400 Bad Request
```json
{"field_name": ["Error message", ...]}
```

### 403 Forbidden
```json
{"detail": "Localized permission message"}
```

### 404 Not Found
```json
{"detail": "Không tìm thấy..."}
```

### 429 Too Many Requests
Throttled — xem retry-after header.

### 503 Service Unavailable
Photo endpoints, lưu trữ không cấu hình.

---

## Chưa Xác Minh

- **Ảnh / S3-R2:** logic đã test với mock `botocore`, **chưa từng chạy với bucket thật**. Cần nghiệm thu: signature version, CORS của bucket, region, Content-Type enforcement, dọn object mồ côi. Mock không bắt được 3 lỗi đầu, và cả 3 đều fail ở bước client `PUT` — chỗ khó quan sát nhất trong luồng.
- **Push nhắc giỗ / FCM:** `POST /devices` nhận và lưu token bình thường, nhưng **chưa có push nào tới máy thật**. Toàn bộ đường FCM chỉ nghiệm thu qua mock. Client đăng ký token thành công KHÔNG có nghĩa là sẽ nhận được thông báo.

---

## Tài Liệu Liên Quan

- **Lunar Calendar**: `docs/system-architecture.md` → "Lunar Calendar"
- **System Architecture**: `docs/system-architecture.md`
- **Code Standards**: `docs/code-standards.md`
- **Codebase Overview**: `docs/codebase-summary.md`
