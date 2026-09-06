---
phase: 9
title: "Chia se cong khai"
status: completed
priority: P2
effort: "1d"
dependencies: [4]
---

# Phase 9: Chia sẻ công khai (`public_slug`) + lọc người còn sống

## Overview
Trưởng họ bật bản công khai của gia phả, chia sẻ bằng link/QR (dán ở nhà thờ họ), người xem không cần đăng nhập. Người còn sống bị ẩn chi tiết.

**Đây là phase có rủi ro rò rỉ PII cao nhất.** Mọi trường hiển thị phải là danh sách trắng, không phải danh sách đen.

## Requirements
- Functional: bật/tắt bản công khai, sinh/thu hồi slug, endpoint công khai không cần auth trả cây đã lọc.
- Non-functional: serializer công khai **tách hoàn toàn** khỏi serializer nội bộ; có test security chặn regression.

## Architecture

### Vì sao serializer tách riêng, không dùng cờ `exclude`
Dùng chung serializer rồi `pop()` vài trường khi công khai là mô hình danh sách đen: thêm một trường mới vào Person ở tương lai → trường đó **tự động bị lộ**. Serializer công khai phải liệt kê tường minh các trường được phép (danh sách trắng), để trường mới mặc định là ẩn.

### Trường được phép công khai

| | Người đã mất | Người còn sống |
|---|---|---|
| `id`, `generation`, `branch`, `is_truong`, `birth_order` | ✅ | ✅ |
| `ho_ten` | ✅ | ✅ (xem cờ bên dưới) |
| `ten_huy`, `ten_tu`, `ten_hieu`, `thuy_hieu` | ✅ | ❌ |
| năm sinh / năm mất | ✅ | ❌ |
| ngày giỗ âm lịch | ✅ | — |
| `tieu_su`, `que_quan`, `nghe_nghiep` | ✅ | ❌ |
| ảnh | ✅ | ❌ |
| toạ độ mộ phần | ❌ (xem rủi ro) | — |

Cờ `Clan.hide_living_details` (mặc định **True**):
- `True` → người sống chỉ còn `id`, vị trí trên cây, và **tên viết tắt** (`"Nguyễn Đình A."`) để cây không đứt đoạn.
- `False` → người sống hiện `ho_ten` đầy đủ, vẫn ẩn ngày sinh/tiểu sử/ảnh.

Không có mức nào cho phép công khai ngày sinh đầy đủ của người còn sống. Ngày sinh + họ tên là bộ đôi dùng để mạo danh.

### Slug
`public_slug` = 22 ký tự ngẫu nhiên `secrets.token_urlsafe(16)`. Đủ dài để không dò được. Thu hồi = sinh slug mới (link cũ chết ngay).

### Rate limit
Endpoint công khai không cần auth → dùng DRF `AnonRateThrottle` với mức riêng (ví dụ `60/hour` theo IP). Không có nó, một script có thể cào toàn bộ gia phả công khai.

## Related Code Files

**Create**
- `giapha/serializers/public.py` — `PublicPersonSerializer`, `PublicTreeSerializer` (danh sách trắng)
- `giapha/views/public.py`
- `giapha/tests/test_public_security.py`

**Modify**
- `giapha/views/clan.py` — `PATCH visibility`, `POST /public-link`, `DELETE /public-link`
- `giapha/selectors/tree.py` — tham số `public=True` để không nạp các trường nhạy cảm **ngay từ query** (phòng thủ nhiều lớp)
- `djangopj/settings.py` — `DEFAULT_THROTTLE_RATES`
- `giapha/urls.py`

## Endpoints
```
POST   /api/gia-pha/clans/{clan_id}/public-link   IsClanOwner -> {slug, url}
DELETE /api/gia-pha/clans/{clan_id}/public-link   IsClanOwner (thu hồi)
GET    /api/gia-pha/public/{slug}/tree            AllowAny + throttle
GET    /api/gia-pha/public/{slug}/persons/{pid}   AllowAny + throttle
```

## Implementation Steps
1. Thêm `POST/DELETE /public-link`. Bật công khai đồng thời set `visibility='public_link'` và sinh slug trong một `transaction.atomic`.
2. `selectors/tree.py` nhận `public=True`: `values()` **chỉ** liệt kê các cột được phép. Người sống bị loại các cột nhạy cảm ngay ở tầng SQL — nếu serializer có lỗi, dữ liệu cũng không có sẵn trong bộ nhớ để lộ.
3. `serializers/public.py` khai báo `fields = (...)` tường minh. **Cấm** `fields = '__all__'` và cấm `exclude`.
4. Rút gọn tên người sống: hàm thuần `abbreviate_name("Nguyễn Đình An") -> "Nguyễn Đình A."` trong `services/`, có test.
5. View công khai: `visibility != 'public_link'` hoặc slug sai → **404** (không phải 403).
6. Thêm throttle scope riêng cho view công khai.
7. Trả header `X-Robots-Tag: noindex, nofollow` ở endpoint công khai. Gia phả bị Google index là chuyện không quay lại được. (Xem câu hỏi mở — nếu chủ dự án **muốn** SEO thì bỏ header này, nhưng phải là quyết định có ý thức.)
8. Test security — đây là phần quan trọng nhất của phase:
   - Người sống không lộ: ngày sinh, tên huý, tiểu sử, quê quán, nghề nghiệp, ảnh, toạ độ mộ
   - Slug sai → 404; clan private → 404
   - Slug đã thu hồi → 404
   - **Test canary**: thêm một trường mới vào `Person` trong test rồi khẳng định nó **không** xuất hiện trong response công khai → chứng minh cơ chế danh sách trắng thật sự hoạt động

## Success Criteria
- [x] No sensitive fields of living persons in public response (whitelist enforced at SQL query level + serializer)
- [x] Test canary: new field added to Person in test → not in public response (proved whitelist mechanism)
- [x] Wrong slug / private clan / revoked slug all return 404 (404-only surface, no 403 to enable enumeration oracle bypass)
- [x] Throttle prevents data scraping (X-Forwarded-For bypass fixed: DJANGO_NUM_PROXIES now required)
- [x] Public endpoints return `X-Robots-Tag: noindex, nofollow` and `Cache-Control: no-store`
- [x] Grave coordinates not in public response (never queried for public persons)
- [x] Public serializer uses explicit `fields` list, no `__all__` or `exclude` (verified by grep in tests)
- [x] Living person given-name rendering (single char → `(Đang sống)` placeholder)
- [x] Marriage edges omitted from public tree (Marriage.status not whitelisted — product decision, no spouse visibility at MVP)

## Risk Assessment
- **Rò rỉ PII là rủi ro nghiêm trọng nhất của cả plan.** Một link công khai chứa họ tên + ngày sinh của hàng trăm người sống là sự cố dữ liệu thật, không phải bug thẩm mỹ.
- **Toạ độ mộ phần công khai = chỉ đường cho trộm mộ.** Có thật ở Việt Nam. Mặc định ẩn hoàn toàn ở bản công khai, không có tuỳ chọn bật ở MVP.
- **Danh sách đen sẽ hỏng theo thời gian.** Bắt buộc danh sách trắng + test canary.
- **Slug bị phát tán không thu hồi lại được.** Cung cấp nút thu hồi ngay từ đầu, và nói rõ với người dùng rằng link cũ chết.
- **Bị cào dữ liệu.** Throttle theo IP là biện pháp tối thiểu, không phải hoàn hảo. Chấp nhận ở MVP.
