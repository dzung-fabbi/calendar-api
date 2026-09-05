# Brainstorm — Chức năng Gia phả dòng họ

- Ngày: 2026-09-05
- Repo: `calendar-api` (Django 3.1 + DRF + MySQL 5.7), branch `master`
- Phạm vi: **backend/API only** — frontend do bên khác lo

---

## 1. Bối cảnh & vấn đề

App hiện là dịch vụ lịch vạn niên VN (hiệp kỷ, thần sát, tiết khí, sao, số học)
+ đặt lịch/nhắc lịch hẹn + membership trả phí (`UserProfile.is_free`).

Cần thêm module **gia phả dòng họ**. Đây là domain nặng nhất từng thêm vào repo,
không dùng chung dữ liệu với almanac. Nhưng đúng chiến lược: app đã có **lịch âm +
xem ngày tốt + nhắc nhở**, mà thứ gia phả cần nhất là **ngày giỗ (kỵ nhật) theo âm lịch**.
Đó là nơi phần lớn giá trị khác biệt nằm.

## 2. Ràng buộc đã chốt

| Hạng mục | Quyết định |
|---|---|
| Phạm vi MVP | Lõi gia phả + lịch giỗ tự động |
| Sở hữu dữ liệu | Riêng tư từng dòng họ + tuỳ chọn bật bản công khai |
| Kiếm tiền | Miễn phí hoàn toàn (không billing trong MVP) |
| Client | Chỉ backend/API |
| Mô hình quan hệ | **A** — FK cha/mẹ + bảng `Marriage` |
| Âm lịch | Viết `vn_lunar` riêng cho gia phả, không đụng almanac |
| Máy tính xưng hô | **Có** trong MVP, tách thành 1 phase riêng |
| Ảnh | Upload qua API lên S3/R2 — dùng **presigned URL** |

## 3. Tính năng

### 3.1 Cần có (MVP)
1. Không gian dòng họ (clan), tạo/tham gia bằng mã mời
2. Phân quyền: owner / editor / viewer
3. Hồ sơ nhân vật: họ tên, **tên húy / tự / hiệu / thụy hiệu**, giới, đời thứ, chi/nhánh,
   trưởng-thứ, ngày sinh & mất (âm + dương), quê quán, nghề, tiểu sử, ảnh
4. Quan hệ: cha/mẹ, vợ/chồng (**đa thê: vợ cả / vợ lẽ**), con ruột / nuôi / kế
5. Dữ liệu cây: API trả `nodes[] + edges[]` phẳng, client tự layout
6. Tìm kiếm & lọc theo tên / đời / chi / năm mất
7. Riêng tư người sống: bản công khai ẩn ngày sinh, liên hệ, tiểu sử
8. Lịch sử chỉnh sửa + khôi phục (`PersonRevision`)

### 3.2 Nổi bật (khác biệt)
1. **Lịch giỗ chạp tự động** — sinh ngày giỗ cả họ theo âm lịch, push nhắc trước N ngày. Chủ lực.
2. **Máy tính xưng hô** — suy ra bác/chú/thím/cô/dì/cậu/mợ/cháu/chắt/chút/chít theo đường đi trên cây. Thuần thuật toán, độ lan toả cao.
3. **Chia sẻ công khai + QR tại từ đường** — quét QR xem cây gia phả bản công khai.

### 3.3 Hoãn (phase sau)
Văn khấn tự sinh · Chọn ngày tốt việc họ (cải táng, tảo mộ, khánh thành từ đường) ·
Bản đồ mộ phần · Xuất PDF · Import Excel · Quỹ họ · OCR gia phả giấy · GEDCOM

### 3.4 Loại bỏ (YAGNI)
Chat trong họ · mạng xã hội dòng họ · DNA · kết nối liên họ toàn quốc

## 4. Các phương án đã cân nhắc

### 4.1 Mô hình quan hệ

| PA | Mô tả | Ưu | Nhược | Kết |
|---|---|---|---|---|
| **A** | `Person.father/mother` FK + `Marriage(husband, wife, order)` | Đơn giản, ràng buộc toàn vẹn tốt, truy vấn thẳng, phủ ~95% ca VN gồm đa thê/tái hôn | Xuất GEDCOM sau phải viết bộ chuyển đổi | **CHỌN** |
| B | Kiểu GEDCOM, node `Family` | Chuẩn quốc tế, xuất/nhập GEDCOM thẳng | Thêm 1 lớp gián tiếp cho mọi truy vấn, trả giá trước cho thứ đã bị loại khỏi MVP | Loại |
| C | Bảng quan hệ tổng quát `(a, b, type)` | Linh hoạt tối đa | Không ràng buộc toàn vẹn, dữ liệu rác chắc chắn, self-join nhiều lần | Loại |

### 4.2 Duyệt cây (MySQL 5.7 **không có** `WITH RECURSIVE`)

| PA | Kết |
|---|---|
| Closure table | Over-engineering ở quy mô này — loại |
| Materialized path | Chưa cần — loại |
| **Nạp cả clan 1 query, duyệt trong Python** | **CHỌN** — clan ≤ 5.000 người chỉ vài chục ms |

`generation` (đời thứ) tính khi ghi và lưu sẵn; đổi cha/mẹ thì tính lại nhánh con.
Trần `MAX_CLAN_PERSONS = 5000` chặn lạm dụng (app miễn phí).

### 4.3 Nhắc giỗ

| PA | Kết |
|---|---|
| Materialize vào `AppointmentDate` cho N năm | Nhân bản dữ liệu, phải backfill khi sửa ngày mất — loại |
| **Command riêng `remind_death_anniversary`, tính trực tiếp mỗi ngày** | **CHỌN** |

### 4.4 Upload ảnh

| PA | Kết |
|---|---|
| Client tự upload, API lưu URL | Mất kiểm soát — loại |
| Bytes đi qua Django rồi lên S3 | Chiếm worker, tốn RAM — loại |
| **Presigned URL: API cấp URL ký sẵn, client PUT thẳng S3/R2, backend ghi key** | **CHỌN** |

## 5. Giải pháp chốt

### 5.1 Vị trí code
Django app **mới** `giapha/`, KHÔNG nhồi vào `apis/` (`apis/` là domain almanac).
Giữ đúng phân lớp của repo: `models/ selectors/ services/ serializers/ views/ admin/ tests/`.
Phụ thuộc một chiều `views -> serializers/selectors/services -> models`; `services/` không import ORM.

### 5.2 Schema (rút gọn)

```
Clan(ten_ho, thuy_to, mo_ta, visibility[private|public_link],
     public_slug, hide_living_details)
ClanMember(clan, user, role[owner|editor|viewer])
ClanInvite(clan, code, expires_at, max_uses)

Person(clan, ho_ten, ten_huy, ten_tu, ten_hieu, thuy_hieu, gioi_tinh,
       father->Person, mother->Person, parent_kind[ruột|nuôi|kế],
       birth_order, is_truong, generation, branch,
       birth_solar, birth_lunar,
       death_solar, death_lunar_day, death_lunar_month, death_lunar_leap,
       que_quan, nghe_nghiep, tieu_su, photo_key,
       mo_phan_lat, mo_phan_lng, mo_phan_note)
Marriage(husband->Person, wife->Person, order[vợ cả=1, lẽ=2..], status, note)
PersonRevision(person, actor, payload_json, created_at)
```

`is_living` suy ra từ `death_* is null` (không lưu cột riêng).

### 5.3 Âm lịch
`giapha/services/vn_lunar.py` — thuật toán Hồ Ngọc Đức, múi giờ **UTC+7**, thuần Python,
không thêm dependency. **Chỉ dùng cho gia phả**; almanac vẫn giữ `lunarcalendar` để không
vỡ golden snapshots. Đây là mâu thuẫn đã biết, chấp nhận có chủ đích, ghi vào docs.

Lý do bắt buộc: `lunarcalendar` là lịch âm TQ (UTC+8), lệch 1 ngày ở một số năm.
Với ngày giỗ, sai 1 ngày là hỏng toàn bộ tính năng.

### 5.4 Bề mặt API (dự kiến, tiền tố `/api/gia-pha/`)

```
POST   clans                          tạo dòng họ
GET    PATCH clans/{id}
POST   clans/{id}/invite              sinh mã mời
POST   join                           tham gia bằng mã
GET    clans/{id}/members
CRUD   clans/{id}/persons
GET    clans/{id}/persons/{pid}
CRUD   clans/{id}/marriages
GET    clans/{id}/tree                nodes[] + edges[] phẳng
GET    clans/{id}/lich-gio?from=&to=  kèm can-chi ngày
GET    clans/{id}/xung-ho?a=&b=       máy tính xưng hô
POST   clans/{id}/photo-upload-url    presigned PUT
GET    public/{slug}/tree             bản công khai, lọc người sống
```

### 5.5 Lộ trình

| Phase | Nội dung |
|---|---|
| 1 | Scaffold app `giapha/` + models + migrations + admin |
| 2 | Clan / ClanMember / Invite + phân quyền |
| 3 | Person + Marriage CRUD + validation |
| 4 | Endpoint `tree` + tính `generation` + tìm kiếm/lọc |
| 5 | `vn_lunar` + endpoint lịch giỗ + command `remind_death_anniversary` |
| 6 | Máy tính xưng hô |
| 7 | Presigned upload ảnh (S3/R2) |
| 8 | Chia sẻ công khai (`public_slug`, lọc người sống) |
| 9 | Test: snapshot shape, query-count ceiling, security/ownership |

## 6. Rủi ro & giảm thiểu

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Âm lịch sai 1 ngày → giỗ sai | **Cao** | `vn_lunar` UTC+7 + bộ test đối chiếu ngày giỗ đã biết |
| Django 3.1 EOL, Python 3.9 pin | **Cao** | Cô lập trong app `giapha/` để nâng cấp sau ít va chạm; nên lên lịch nâng Django song song |
| MySQL 5.7 không có CTE đệ quy | Trung bình | Duyệt trong Python + trần 5.000 người/clan |
| Chu trình cha-con (A là cha của B, B là cha của A) | Trung bình | Validate khi ghi: chặn chu trình, cha sinh trước con, ngày mất ≥ ngày sinh |
| PII người còn sống lộ qua bản công khai | **Cao** | `hide_living_details` mặc định bật; serializer công khai tách riêng; có test security |
| Chi phí storage ảnh (app miễn phí) | Trung bình | Giới hạn kích thước/số ảnh mỗi người, dọn key mồ côi |
| Xoá nhầm cả nhánh | Trung bình | `PersonRevision` + soft delete |
| Tranh chấp dữ liệu giữa các chi | Trung bình | Phân quyền editor + lịch sử chỉnh sửa |

## 7. Tiêu chí thành công
- Nhập được một dòng họ thật ≥ 200 người, 5+ đời, có đa thê, không bí bách
- `GET tree` cho clan 1.000 người: **≤ 3 query**, p95 < 500ms
- Lịch giỗ khớp 100% với danh sách giỗ do trưởng họ xác nhận thủ công (bộ mẫu ≥ 30 ca)
- Bản công khai không rò bất kỳ trường nhạy cảm nào của người sống (test security chặn)
- Query-count ceiling test xanh cho mọi endpoint mới

## 8. Bước tiếp theo
1. Chốt lịch nâng cấp Django (song song hay sau)
2. Chạy `/ck:plan` để bung 9 phase thành file phase chi tiết
3. Cập nhật `docs/system-architecture.md` — thêm app `giapha/` và ghi chú mâu thuẫn âm lịch

## 9. Câu hỏi chưa giải quyết
1. **Kích thước dòng họ lớn nhất thực tế?** Trần 5.000 là phỏng đoán; nếu có clan 20.000 người thì phải chuyển sang materialized path.
2. **S3 hay R2?** Ảnh hưởng credential, SDK (boto3 dùng được cho cả hai) và chi phí egress.
3. **Nâng Django trước hay sau gia phả?** Làm sau nghĩa là migrate cả schema mới.
4. **Bản công khai có bị search engine index không?** Nếu có thì cần quy tắc `robots`/SEO và rà lại PII.
5. **Đa ngôn ngữ / chữ Hán-Nôm cho tên húy?** Ảnh hưởng collation cột (`utf8_unicode_ci` hiện tại có đủ không).
6. **Ai được xoá dòng họ và dữ liệu giữ lại bao lâu?** Chính sách lưu trữ chưa xác định.
