# Generic S3 File Upload API (`apis/`)

## Context

Yêu cầu: "tạo api upload file lên S3 và trả về url file".

Project **đã có** hạ tầng S3 hoàn chỉnh, nhưng nằm trong `giapha/`:

- `giapha/services/storage.py` — boto3 (S3 **và** Cloudflare R2), `presign_put()`, `presign_get()`, `head()`, `delete()`, client cache theo config tuple, `is_configured()`.
- `giapha/views/photo.py` + `photo_urls.py` — 4 endpoint presigned cho `Person.photo_key`.
- `S3_*` settings đã khai báo global ở `djangopj/settings.py:221-225` → `apis/` đọc được ngay, **không cần config mới**.

Luồng hiện có là **presigned 3 bước có chủ ý**: xin presigned `PUT` → client `PUT` thẳng lên S3 → confirm để server `head()` xác minh. Lý do ghi trong docstring `services/storage.py`: đẩy bytes qua Django giữ chặt gunicorn sync worker suốt thời gian upload; vài upload 5MB đồng thời là đủ nghẽn mọi request khác.

Plan này thêm một endpoint **generic** (không gắn model nào) trong app `apis/`, theo đúng luồng presigned đó.

### Đảo một quyết định cũ

`plans/260906-2137-account-auth-apis/plan.md` chốt: *"Avatar — plain `avatar_url` field. **No S3 code** — `giapha/services/storage.py` is not duplicated."*

Plan này **đảo lại**: `apis/services/storage.py` sẽ là bản copy. Lý do: `docs/code-standards.md` → Decoupling cấm `apis/` import `giapha/`, và ưu tiên duplicate hơn dependency chéo app. Cái giá là ~150 dòng nhân đôi, phải sửa hai nơi khi đổi logic storage.

### Quyết định đã chốt với user

| Điểm | Chọn |
|---|---|
| Luồng upload | **Presigned 2 bước** — bytes không qua Django |
| App | `apis/` — copy storage service (không import chéo) |
| URL trả về | **Presigned GET, TTL 1h**. Bucket giữ **private** |
| Content-type | Chỉ ảnh: `image/jpeg`, `image/png`, `image/webp` |
| Size cap | **5MB**, chặn thật ở confirm qua `head()` |
| Auth | **AllowAny** + throttle scope `file-upload` |
| Key | `uploads/{uuid32}.{ext}` — phẳng, không scope user |

### Rủi ro user đã được cảnh báo và chấp nhận

`AllowAny` nghĩa là bất kỳ ai ghi được object vào bucket, chỉ chặn bằng throttle **per-IP** — mà `djangopj/settings.py` (khối `REST_FRAMEWORK`) đã ghi rõ per-IP không phải rào cản thật: `NUM_PROXIES=0`, và nhiều IP nguồn thì vượt qua dễ dàng. Hệ quả có thể: chi phí storage/bandwidth do người lạ tạo, và object rác không có job dọn.

Allowlist chỉ-ảnh là cái giảm nhẹ chính: kẻ lạ không host được `html`/`svg`/`exe`. Confirm `head()` kiểm `ContentType` thật của object, không tin `content_type` client khai ở bước 1.

## Ràng buộc bắt buộc

1. **`apis/` không được import `giapha/`** (`docs/code-standards.md` → Decoupling).
2. `services/` **không chạm ORM**, không nhận `request` — endpoint này vốn không cần DB.
3. File **dưới 200 dòng** (`docs/code-standards.md` → Files).
4. **Không blanket `except Exception`**; phân biệt lỗi *cấu hình* (503) và lỗi *thời tiết* (500) — đúng như bản `giapha`.
5. Mỗi endpoint mới **phải có dòng trong `apis/tests/test_query_counts.py`** — "the ceiling is the contract".
6. `python manage.py makemigrations apis --check --dry-run` phải sạch — plan này **không thêm model nào**.
7. Envelope `{"data": ...}`; 400 trả dict lỗi DRF thô; prose tiếng Việt, slug/code ASCII.
8. Thiếu S3 config → **503**, phần còn lại của API không ảnh hưởng.
9. **Không sửa gì trong `giapha/`** — 4 endpoint ảnh hiện tại phải chạy y nguyên.

## Endpoints

| Method | Path | Auth | Body | Success |
|---|---|---|---|---|
| `POST` | `/api/files/upload-url` | — (throttled) | `content_type`, `size` | `200 {"data": {"upload_url", "key", "expires_in": 300}}` |
| `POST` | `/api/files/confirm` | — (throttled) | `key` | `200 {"data": {"key", "url", "expires_in": 3600}}` |

Luồng client:

```
1) POST /api/files/upload-url  {content_type: "image/jpeg", size: 123456}
   -> {data: {upload_url, key, expires_in: 300}}
2) PUT <upload_url>  (bytes, header Content-Type khớp content_type đã khai)
3) POST /api/files/confirm  {key}
   -> {data: {key, url: "<presigned GET 1h>", expires_in: 3600}}
```

Client lưu `key` nếu cần dùng lại; gọi lại `confirm` để lấy URL mới khi link hết hạn.

## Acceptance criteria

**`POST /api/files/upload-url`**
1. Body hợp lệ → 200, `upload_url` là presigned PUT, `key` khớp `uploads/{32 hex}.{jpg|png|webp}`, `expires_in == 300`.
2. `content_type` ngoài allowlist → 400.
3. `size` > 5MB hoặc < 1 → 400.
4. Thiếu field → 400.

**`POST /api/files/confirm`**
5. Key server vừa mint + object có thật, ≤5MB, content-type hợp lệ → 200, `url` là presigned GET, `expires_in == 3600`.
6. Key sai hình dạng (traversal `../`, thiếu extension, extension lạ, newline, prefix khác) → 400.
7. Object không tồn tại (`head()` trả `None`) → 400.
8. Object > 5MB → 400 (đây là chỗ cap được thực thi thật).
9. `ContentType` thật của object ngoài allowlist → 400.

**Chung**
10. Chưa cấu hình S3 → **503** ở cả hai endpoint.
11. Throttle scope `file-upload` áp cho cả hai.
12. Cả hai endpoint dùng **0 query DB**.
13. Không regression `giapha`; `makemigrations --check` sạch; toàn bộ test cũ pass.

## Non-goals

- **Không** model/bảng DB, không lưu lịch sử file.
- **Không** endpoint delete, **không** job dọn object rác (giapha cũng chưa có).
- **Không** sửa 4 endpoint ảnh của `giapha`.
- Bucket **giữ private** — không sinh URL public vĩnh viễn.
- **Không** gắn file vào `Person`/`UserProfile`.
- Không refactor `giapha/services/storage.py` thành shared package.

## Phases

### Phase 1 — Storage service (copy) + exception

**Files:**
- `apis/services/storage.py` *(mới, ~130 dòng)* — copy từ `giapha/services/storage.py`, **bỏ `delete()`** (không có endpoint delete trong scope). Giữ: `StorageNotConfigured`, `_setting`, `_config`, `is_configured`, `reset_client_cache`, `_client`, `_bucket`, `presign_put`, `presign_get`, `head`. Docstring đầu file phải nêu rõ: đây là bản song sinh có chủ ý của bản `giapha`, lý do (Decoupling rule), và **sửa một bên thì phải sửa bên kia**.
- `apis/exceptions.py` *(sửa)* — thêm `ServiceUnavailableException` (503). Bản `apis` hiện chỉ có `BadRequestException`.

**Xong khi:** import được, `is_configured()` trả `False` với env rỗng.

### Phase 2 — Serializers + hằng số

**Files:**
- `apis/serializers/file_upload.py` *(mới)* — `ALLOWED_CONTENT_TYPES = ('image/jpeg','image/png','image/webp')`, `MAX_FILE_BYTES = 5*1024*1024`, `FileUploadUrlRequestSerializer` (`content_type` ChoiceField, `size` IntegerField min 1 max `MAX_FILE_BYTES`), `FileConfirmSerializer` (`key` CharField max 512).
- `apis/serializers/__init__.py` *(sửa)* — re-export phẳng theo pattern hiện có.

Allowlist đặt ở serializer (không ở service) — giữ `services/` sạch khỏi validation kiểu HTTP, đúng như `giapha/serializers/photo.py:13` ghi.

### Phase 3 — Views + routing + throttle

**Files:**
- `apis/views/file_upload.py` *(mới, ~120 dòng)* — `FileUploadUrlAPIView`, `FileConfirmAPIView`. Cả hai: `permission_classes = [AllowAny]`, `throttle_classes = [ScopedRateThrottle]`, `throttle_scope = 'file-upload'` (pattern y như `giapha/views/clan_membership.py:146-148`). `require_storage()` → 503. `_KEY_RE` build extension alternation **từ** `_EXTENSION_BY_CONTENT_TYPE.values()` để regex không lệch khỏi cái mint ra (đúng lý do ghi ở `giapha/views/photo.py:60-72`).
- `apis/views/__init__.py` *(sửa)* — re-export + `__all__`.
- `apis/urls.py` *(sửa)* — 2 path.
- `djangopj/settings.py` *(sửa)* — thêm `'file-upload': '20/hour'` vào `DEFAULT_THROTTLE_RATES`, kèm comment nêu giới hạn per-IP (nhất quán với các comment quanh đó).

**Xong khi:** acceptance 1-11 pass bằng tay/curl.

### Phase 4 — Tests

**Files:**
- `apis/tests/test_file_upload_api.py` *(mới)* — mock `apis.services.storage.boto3.client` + gọi `reset_client_cache()` trong `setUp`, `@override_settings(**S3_TEST_SETTINGS)`; theo đúng khuôn `giapha/tests/test_photo_api.py:55-75`. Phủ acceptance 1-11, gồm cả nhánh 503 khi `S3_*` rỗng.
- `apis/tests/test_query_counts.py` *(sửa)* + `apis/tests/snapshots/query_budgets.json` *(sửa)* — thêm `file_upload_url` và `file_confirm`, budget **0**.

**Xong khi:** `manage.py test apis giapha` xanh toàn bộ.

### Phase 5 — Docs

**Files:**
- `docs/api-reference.md` *(sửa)* — thêm mục file-upload cạnh khối account `apis/` (quanh dòng 44, chỗ đã ghi "Các endpoint quản lý tài khoản nằm ở app `apis/`"). Ghi rõ: luồng 2 bước, allowlist, cap 5MB thực thi ở confirm, URL presigned 1h, **AllowAny + throttle và giới hạn của nó**.
- `docs/deployment-guide.md` *(sửa)* — ghi chú endpoint mới dùng chung `S3_*` với giapha; nhắc CORS bucket phải cho `PUT` từ origin client (mục CORS đã có sẵn cho giapha).
- `docs/codebase-summary.md` *(sửa)* — thêm `apis/services/storage.py` và `apis/views/file_upload.py`; nêu chuyện song sinh có chủ ý với bản giapha.

**Xong khi:** docs khớp code, không file nào vượt 800 dòng.

## Blast radius

| Đụng tới | Rủi ro | Cách chặn |
|---|---|---|
| `djangopj/settings.py` `DEFAULT_THROTTLE_RATES` | Chỉ **thêm** key. Không set `DEFAULT_THROTTLE_CLASSES` → view khác vẫn không throttle | Test cũ của `apis`/`giapha` phải pass y nguyên |
| `apis/exceptions.py` | Chỉ thêm class mới | `BadRequestException` không đổi |
| `apis/views/__init__.py`, `apis/serializers/__init__.py`, `apis/urls.py` | Chỉ thêm dòng | Import cũ giữ nguyên |
| `giapha/` | **Không sửa gì** | `manage.py test giapha` xanh |
| Migrations | Không thêm model | `makemigrations apis --check --dry-run` sạch |

## Câu hỏi còn mở

1. **Object rác không có ai dọn.** Ai gọi `upload-url` rồi không confirm sẽ để lại object mồ côi, và `AllowAny` khiến chuyện đó rẻ với người lạ. Scope này không có delete/cleanup. Cần lifecycle rule trên bucket (vd expire prefix `uploads/` sau N ngày) không? Đó là việc cấu hình bucket, ngoài code.
2. **Throttle `20/hour` là con số tôi đề xuất**, không phải bạn chốt. Muốn khác không?
