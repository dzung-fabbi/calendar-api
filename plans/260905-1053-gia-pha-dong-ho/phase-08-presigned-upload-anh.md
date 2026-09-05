---
phase: 8
title: "Presigned upload anh"
status: pending
priority: P2
effort: "1d"
dependencies: [3]
---

# Phase 8: Upload ảnh bằng presigned URL (S3/R2)

## Overview
API cấp URL ký sẵn để client PUT ảnh thẳng lên object storage; backend chỉ lưu key và cấp URL đọc. **Không byte nào đi qua Django.**

## Requirements
- Functional: xin URL upload, client PUT, xác nhận, ảnh hiện trong hồ sơ và trên node cây; xoá ảnh.
- Non-functional: Django không nhận file; giới hạn kích thước và kiểu file được **ép ở tầng presign**, không chỉ kiểm tra ở client.

## Architecture

### Vì sao presigned URL
Đẩy bytes qua Django nghĩa là mỗi ảnh 5MB chiếm một worker trong vài giây — với gunicorn sync worker (mặc định) đây là cách nhanh nhất để làm sập API bằng vài người dùng upload cùng lúc. Presign đẩy toàn bộ băng thông sang S3/R2.

### Luồng
```
1. Client: POST /persons/{pid}/photo-upload-url {content_type, size}
2. Server: kiểm quyền editor + validate content_type/size
           sinh key = giapha/{clan_id}/{person_id}/{uuid4}.{ext}
           trả {upload_url, key, expires_in: 300}
3. Client: PUT upload_url với đúng Content-Type
4. Client: PATCH /persons/{pid} {photo_key: key}
5. Server: HEAD lên object để xác nhận tồn tại + đúng kích thước, rồi mới ghi photo_key
```

Bước 5 là bắt buộc. Không có nó, client có thể gán một `photo_key` bịa ra, hoặc gán key của clan khác.

### Đọc ảnh
- Bucket **private**. `photo_url` trong response là **presigned GET**, TTL 1 giờ.
- Node cây trả `photo_url` cho tối đa N node? **Không** — sinh 1.000 presigned URL mỗi lần gọi `/tree` là lãng phí. Cây chỉ trả `has_photo: bool`; URL thật lấy khi mở hồ sơ, hoặc qua endpoint lô `POST /photo-urls {person_ids: [...]}` giới hạn 100 id.

### Cấu hình
```
S3_ENDPOINT_URL       # R2: https://<account>.r2.cloudflarestorage.com; S3: để trống
S3_BUCKET
S3_ACCESS_KEY_ID
S3_SECRET_ACCESS_KEY
S3_REGION             # R2 dùng "auto"
```
`boto3` dùng được cho **cả** S3 và R2 (R2 tương thích S3 API) — không cần SDK riêng. Chọn S3 hay R2 chỉ là đổi biến môi trường.

### Giới hạn
- `content_type` ∈ {`image/jpeg`, `image/png`, `image/webp`}
- `size` ≤ 5MB — ép bằng `Conditions` `content-length-range` trong presign, **không** chỉ tin số client gửi
- ≤ 1 ảnh chân dung / person ở MVP (album ảnh là YAGNI)

## Related Code Files

**Create**
- `giapha/services/storage.py` — `presign_put(key, content_type, max_bytes)`, `presign_get(key)`, `head(key)`, `delete(key)`
- `giapha/views/photo.py`
- `giapha/tests/test_photo_api.py`

**Modify**
- `requirements.txt` — thêm `boto3`
- `.env.example` — 5 biến ở trên
- `djangopj/settings.py` — đọc 5 biến
- `giapha/serializers/person.py` — thêm `photo_url` (chỉ ở serializer chi tiết), `has_photo` (ở serializer cây)
- `giapha/views/person.py` — xác nhận HEAD trước khi ghi `photo_key`; xoá object cũ khi thay ảnh

## Endpoints
```
POST /api/gia-pha/clans/{clan_id}/persons/{pid}/photo-upload-url   IsClanEditor
POST /api/gia-pha/clans/{clan_id}/photo-urls                       IsClanMember  {person_ids: [...]}
DELETE /api/gia-pha/clans/{clan_id}/persons/{pid}/photo            IsClanEditor
```

## Implementation Steps
1. `services/storage.py` bọc `boto3.client('s3', endpoint_url=...)`. Client khởi tạo **một lần** ở module level (tạo client mỗi request là chậm đáng kể).
2. Presign PUT dùng `generate_presigned_url('put_object', ...)` với `ContentType` cố định, TTL 300s.
3. Key luôn có `clan_id` ở tiền tố → dễ xoá cả clan sau này, và dễ kiểm chứng key thuộc đúng clan ở bước xác nhận.
4. Xác nhận: `head_object` — kiểm tra `ContentLength` ≤ 5MB và key khớp tiền tố `giapha/{clan_id}/{person_id}/`. Sai → 400.
5. Thay ảnh: ghi key mới rồi mới xoá object cũ (thứ tự này an toàn hơn; nếu xoá lỗi thì chỉ còn rác, không mất ảnh).
6. `DELETE /photo`: xoá object + set `photo_key=''`.
7. Thiếu cấu hình storage → các endpoint ảnh trả **503 kèm thông báo rõ**, phần còn lại của API vẫn chạy bình thường.
8. Test: **mock boto3 hoàn toàn**, không gọi mạng. Phủ: content_type sai, size vượt, key thuộc clan khác, thiếu cấu hình.
9. Ghi chú vào `docs/deployment-guide.md`: bucket phải private, và cần cấu hình CORS cho phép PUT từ origin của app.

## Success Criteria
- [ ] Upload ảnh end-to-end thành công với bucket thật (kiểm thủ công một lần)
- [ ] Không có byte ảnh nào đi qua Django (kiểm bằng đọc code + log)
- [ ] `photo_key` của clan khác bị từ chối
- [ ] File > 5MB bị S3 từ chối do `content-length-range`, không phải chỉ do client tự giác
- [ ] `/tree` **không** sinh presigned URL hàng loạt
- [ ] Thiếu cấu hình storage → 503 ở endpoint ảnh, API còn lại vẫn 200
- [ ] Test không chạm mạng

## Risk Assessment
- **CORS trên bucket là chỗ hay quên.** Không cấu hình thì client PUT sẽ fail mà lỗi lại khó đọc. Ghi vào deployment guide ngay.
- **Rác object.** Client xin presign rồi bỏ dở → object mồ côi hoặc key không bao giờ được xác nhận. Chấp nhận ở MVP; ghi chú cần một job dọn định kỳ về sau (chưa làm — YAGNI).
- **Bucket để public là lỗi lộ PII.** Ảnh gia đình + bucket công khai + key đoán được = rò rỉ. Bắt buộc private + presigned GET.
- **TTL của presigned GET.** 1 giờ là cân bằng giữa cache được ở client và không phát tán link vĩnh viễn.
- **Cần tài sản bên ngoài**: bucket + credential. Chưa có thì phase này bị chặn — xác nhận sớm.
