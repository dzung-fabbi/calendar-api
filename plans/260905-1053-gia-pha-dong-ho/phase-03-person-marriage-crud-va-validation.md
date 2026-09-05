---
phase: 3
title: "Person Marriage CRUD va validation"
status: completed
priority: P1
effort: "2d"
dependencies: [2]
---

# Phase 3: Person + Marriage CRUD + validation + revision

## Overview
CRUD cho nhân vật và hôn nhân, cùng bộ validation bảo vệ tính toàn vẹn của cây — đây là phase quyết định chất lượng dữ liệu của cả module.

## Requirements
- Functional: thêm/sửa/xoá mềm Person; gắn cha/mẹ; tạo/sửa Marriage kèm `order` (vợ cả / vợ lẽ); mọi thay đổi ghi `PersonRevision`; khôi phục được bản trước.
- Non-functional: validation nằm ở `services/`, thuần Python, test bằng `SimpleTestCase`; view không chứa logic nghiệp vụ.

## Architecture

### Bộ luật validation (`services/person_rules.py`)

Toàn bộ là hàm thuần, nhận dict/tuple thay vì model instance ở chỗ nào làm được:

| Luật | Mô tả | Vi phạm |
|---|---|---|
| `no_cycle` | Cha/mẹ mới không được nằm trong tập hậu duệ của chính person | 400 |
| `parent_in_same_clan` | father/mother phải cùng `clan_id` | 400 |
| `parent_born_before_child` | Nếu biết cả hai ngày sinh, cha/mẹ phải sinh trước con **ít nhất 12 năm** | 400 |
| `death_after_birth` | `death_solar >= birth_solar` | 400 |
| `lunar_death_valid` | `death_lunar_month` ∈ 1..12, `death_lunar_day` ∈ 1..30 | 400 |
| `death_pair_complete` | Có `death_lunar_day` thì phải có `death_lunar_month` và ngược lại | 400 |
| `self_not_parent` | `father_id != id`, `mother_id != id` | 400 |
| `clan_size_cap` | Số Person chưa xoá của clan < `MAX_CLAN_PERSONS` | 400 |
| `marriage_distinct` | `husband_id != wife_id`, cùng clan | 400 |
| `marriage_order_unique` | Trong cùng một `husband`, `order` không trùng | 400 |

**`no_cycle` là luật quan trọng nhất.** Một chu trình cha-con làm mọi thuật toán duyệt ở phase 4/7 lặp vô hạn. Cài đặt: lấy tập hậu duệ của person bằng BFS trong bộ nhớ (1 query nạp `(id, father_id, mother_id)` của cả clan — dùng `.values_list()`, không nạp full model), rồi kiểm tra ứng viên cha/mẹ có nằm trong tập đó không.

Cảnh báo: `parent_born_before_child` dùng ngưỡng 12 năm — dữ liệu gia phả cũ hay sai lệch, nên đây là **cảnh báo cứng chặn ghi**, và cần một cờ `force=true` cho owner ghi đè khi dữ liệu tổ tiên thật sự bất thường. Không có cờ này thì người dùng sẽ mắc kẹt.

### Ghi lịch sử
Decorator/helper `record_revision(person, actor, action)` trong `services/revision.py`:
- Chụp snapshot **trước** khi đổi, `json.dumps` các trường của Person (bỏ `created_at/updated_at`).
- `DELETE` = soft delete (`is_deleted=True`), không xoá vật lý.
- Xoá một Person đang là cha/mẹ của người khác → **400**, buộc gỡ liên kết con trước. Không tự động set `father=None` hàng loạt (dễ mất dữ liệu âm thầm).

## Related Code Files

**Create**
- `giapha/services/person_rules.py`
- `giapha/services/revision.py`
- `giapha/selectors/person.py` — `clan_edges(clan_id)` trả `[(id, father_id, mother_id)]`, dùng lại ở phase 4/7
- `giapha/serializers/person.py`, `giapha/serializers/marriage.py`
- `giapha/views/person.py`, `giapha/views/marriage.py`
- `giapha/tests/test_person_rules.py` (SimpleTestCase, không DB)
- `giapha/tests/test_person_api.py`

**Modify**
- `giapha/urls.py`

## Endpoints

```
GET    /api/gia-pha/clans/{clan_id}/persons              IsClanMember  (phân trang)
POST   /api/gia-pha/clans/{clan_id}/persons              IsClanEditor
GET    /api/gia-pha/clans/{clan_id}/persons/{pid}        IsClanMember
PATCH  /api/gia-pha/clans/{clan_id}/persons/{pid}        IsClanEditor
DELETE /api/gia-pha/clans/{clan_id}/persons/{pid}        IsClanEditor (soft)
GET    /api/gia-pha/clans/{clan_id}/persons/{pid}/revisions   IsClanEditor
POST   /api/gia-pha/clans/{clan_id}/persons/{pid}/restore/{rev_id}  IsClanEditor

GET    /api/gia-pha/clans/{clan_id}/marriages            IsClanMember
POST   /api/gia-pha/clans/{clan_id}/marriages            IsClanEditor
PATCH  /api/gia-pha/clans/{clan_id}/marriages/{mid}      IsClanEditor
DELETE /api/gia-pha/clans/{clan_id}/marriages/{mid}      IsClanEditor
```

## Implementation Steps
1. Viết `selectors/person.py::clan_edges(clan_id)` — `Person.objects.filter(clan_id=..., is_deleted=False).values_list('id','father_id','mother_id')`. Một query, không nạp full row.
2. Viết `services/person_rules.py`. Mọi hàm nhận dữ liệu thô (list edge, dict payload), **không** nhận queryset → test không cần DB.
   - `descendants(edges, root_id) -> set[int]` bằng BFS, có bộ đếm bảo hiểm chống lặp vô hạn nếu dữ liệu cũ đã có chu trình.
3. Viết `services/revision.py::snapshot(person) -> str` và `record(person, actor, action)`.
4. Serializers: `PersonWriteSerializer` (nhận `father_id`, `mother_id` dạng số) tách khỏi `PersonReadSerializer` (nhúng tên cha/mẹ để client khỏi phải join). Tách hai lớp giúp phase 9 làm serializer công khai dễ hơn.
5. Views: bọc mọi thao tác ghi trong `transaction.atomic`; gọi validate → ghi revision → ghi Person.
6. `POST /persons` hỗ trợ **ghi hàng loạt** (nhận list) — nhập một dòng họ 200 người từng người một qua HTTP là không dùng được. Giới hạn 200 bản ghi/lần.
7. Marriage: `order` mặc định = `max(order hiện có của husband) + 1`. `order=1` mang nghĩa vợ cả.
8. Test `test_person_rules.py`: mỗi luật ≥ 1 ca hợp lệ + 1 ca vi phạm. Ca chu trình phải gồm cả chu trình gián tiếp A→B→C→A.
9. Test `test_person_api.py`: viewer bị 403 khi ghi; editor của clan khác bị 404; ghi hàng loạt; soft delete không biến mất khỏi revisions.

## Success Criteria
- [x] Không thể tạo chu trình cha-con, kể cả gián tiếp qua 3+ đời
- [x] Không thể gắn cha/mẹ thuộc clan khác
- [x] Xoá Person đang là cha/mẹ bị chặn với thông báo nêu rõ số con đang tham chiếu
- [x] Khôi phục từ `PersonRevision` trả đúng dữ liệu trước đó — **lưu ý:** restore sau review được bổ sung validate cycle, không cho restore tạo chu trình
- [x] Ghi hàng loạt 200 người trong 1 request thành công
- [x] `test_person_rules.py` chạy bằng `SimpleTestCase` (không chạm DB)
- [x] Vượt `MAX_CLAN_PERSONS` bị chặn

## Deviations from spec

**`views/person.py` split into `views/person.py` + `views/person_list.py` + `views/person_revision.py`.** Spec planned single `views/person.py`, but file size management required splitting: `person.py` has detail API, `person_list.py` has list/create/bulk-create + search/filter, `person_revision.py` has revisions list + restore. Each stays <200 LOC.

**`record()` moved to `selectors/revision.py`.** Spec placed it in `services/revision.py`, but the function needs to save to DB (ORM call `PersonRevision.objects.create()`), violating the `services/` purity guarantee ("không có behaviour, không import ORM"). Relocated to `selectors/revision.py` where DB queries live. `services/revision.py` kept pure with `snapshot()` and `restore()` (no ORM).

**Restore does NOT undelete.** After review, restore was enhanced to validate cycles and exclude `is_deleted`/`clan_id` from the restoration (they no longer restore). Restoring a person always leaves `is_deleted` as-is.

**Phase 3 generation compute:** Implementation omitted computing `generation` on person create (both single and bulk). Fixed in review-and-fix cycle; now computes on create too.

## Risk Assessment
- **Chu trình cha-con là lỗi chí mạng** — làm treo phase 4 (tính generation) và phase 7 (tìm đường xưng hô). Validate ở tầng ghi là chưa đủ nếu dữ liệu được nhập thẳng qua admin; thêm bộ đếm bảo hiểm trong mọi hàm duyệt.
- **`parent_born_before_child` quá nghiêm sẽ chặn dữ liệu thật.** Bắt buộc có cờ `force` cho owner, nếu không người dùng bỏ app.
- **Ghi hàng loạt + validate chu trình**: validate từng bản ghi sẽ tốn N query. Nạp `clan_edges` **một lần** cho cả lô, cập nhật tập edge trong bộ nhớ khi duyệt lô.
- **Soft delete và tính toàn vẹn cây**: người đã xoá mềm vẫn là `father_id` của con → mọi selector phải lọc `is_deleted=False` một cách nhất quán, nếu không cây sẽ đứt đoạn im lặng.
