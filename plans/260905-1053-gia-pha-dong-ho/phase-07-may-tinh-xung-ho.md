---
phase: 7
title: "May tinh xung ho"
status: pending
priority: P2
effort: "1.5d"
dependencies: [4]
---

# Phase 7: Máy tính xưng hô

## Overview
Cho hai người bất kỳ trong dòng họ, tính ra cách xưng hô tiếng Việt: "bạn gọi người này là **bác**, người này gọi bạn là **cháu**".

Thuần thuật toán, không thêm hạ tầng. Đây là tính năng dễ lan truyền nhất của module.

## Requirements
- Functional: nhập 2 person_id → trả cặp `(A gọi B là ..., B gọi A là ...)` + đường quan hệ để giải thích.
- Non-functional: `services/kinship.py` thuần Python, `SimpleTestCase`; endpoint ≤ 2 query.

## Architecture

### Cách tính
1. Tìm **tổ tiên chung gần nhất** (LCA) của A và B trên đồ thị cha/mẹ. Cây gia phả không phải cây nhị phân và có thể nhiều gốc → dùng: dựng tập tổ tiên của A kèm độ sâu, rồi BFS từ B lên cho tới khi chạm tập đó.
2. Từ LCA có hai khoảng cách: `da` (số đời từ LCA xuống A), `db` (xuống B).
3. Ánh xạ `(da, db, giới tính, bên nội/ngoại, thứ bậc anh/em của hai nhánh)` → từ xưng hô.

### Dữ liệu quyết định từ xưng hô (đây mới là phần khó, không phải LCA)

| Trường hợp | Cần biết thêm | Từ |
|---|---|---|
| `da == db == 1` (anh chị em ruột/họ) | ai sinh trước | anh / chị / em |
| `da == 2, db == 1`, nhánh B là **anh** của cha A | — | **bác** |
| `da == 2, db == 1`, nhánh B là **em trai** của cha A | — | **chú** |
| `da == 2, db == 1`, nhánh B là **em gái** của cha A | — | **cô** |
| `da == 2, db == 1`, bên **mẹ**, nam | — | **cậu** |
| `da == 2, db == 1`, bên **mẹ**, nữ | — | **dì** |
| vợ của chú | quan hệ hôn nhân | **thím** |
| vợ của cậu | quan hệ hôn nhân | **mợ** |
| chồng của cô/dì | quan hệ hôn nhân | **chú / dượng** |
| `da == 1, db == 2` (chiều ngược) | — | **cháu** |
| chênh 3 đời | — | **chắt** (hoặc cụ/cố ở chiều ngược) |
| chênh 4 / 5 đời | — | **chút** / **chít** |
| lên 2/3/4 đời | — | **ông-bà / cụ / kỵ** |

**Ba dữ kiện bắt buộc mà thuật toán phụ thuộc:**
1. **Bên nội hay bên ngoại** — suy từ việc bước lên bằng `father` hay `mother` ở mắt xích đầu tiên từ A.
2. **Thứ bậc anh/em giữa hai nhánh tại LCA** — cần `birth_order` của hai người con của LCA. **Nếu `birth_order` thiếu, không phân biệt được bác với chú.** Đây là hạn chế dữ liệu, không phải hạn chế thuật toán.
3. **Quan hệ hôn nhân** — thím/mợ/dượng chỉ ra được khi đi qua cạnh `Marriage`.

Khi thiếu dữ liệu: trả từ **trung tính kèm cờ**, ví dụ `{"term": "bác/chú", "confident": false, "reason": "thiếu birth_order"}`. **Không đoán bừa** — đoán sai vai vế là điều người Việt để bụng.

### Response
```json
{
  "a_calls_b": {"term": "bác", "confident": true},
  "b_calls_a": {"term": "cháu", "confident": true},
  "common_ancestor": {"id": 3, "ho_ten": "Nguyễn Đình Tổ"},
  "path": {"a_up": 2, "b_up": 1, "side": "noi"},
  "explain": "Bác là anh trai của bố bạn."
}
```

## Related Code Files

**Create**
- `giapha/services/kinship.py` — LCA + bảng ánh xạ
- `giapha/services/kinship_terms.py` — dữ liệu bảng từ vựng, tách khỏi thuật toán (file dữ liệu, dễ sửa)
- `giapha/views/kinship.py`
- `giapha/tests/test_kinship.py` (SimpleTestCase, nhiều ca)

**Modify**
- `giapha/urls.py`
- dùng lại `giapha/selectors/person.py::clan_edges` từ phase 3

## Endpoints
```
GET /api/gia-pha/clans/{clan_id}/xung-ho?a={pid}&b={pid}   IsClanMember
```

## Implementation Steps
1. Mở rộng `clan_edges` để trả thêm `birth_order` và `gioi_tinh` (vẫn 1 query).
2. `services/kinship.py::lowest_common_ancestor(edges, a, b) -> (ancestor_id, depth_a, depth_b, side)`. Có bộ đếm bảo hiểm chống chu trình.
3. `kinship_terms.py`: bảng tra dạng dict, khoá là tuple `(da, db, side, gender, elder)`. Dữ liệu thuần, không logic.
4. `resolve_term(...)` tra bảng; không khớp thì lùi về quy tắc chung theo số đời chênh lệch (`cháu/chắt/chút/chít`, `ông/cụ/kỵ`).
5. Xử lý cạnh hôn nhân: nếu B không có quan hệ máu mủ với A nhưng là vợ/chồng của người có quan hệ máu mủ → tính từ người đó rồi chuyển sang từ dâu/rể tương ứng (thím, mợ, dượng).
6. Không tìm được tổ tiên chung → trả `{"term": null, "reason": "khong_cung_huyet_thong"}`, HTTP 200 (không phải lỗi).
7. Test: tối thiểu 25 ca phủ hết bảng ánh xạ, gồm cả ca thiếu `birth_order` (phải trả `confident: false`) và ca A == B.

## Success Criteria
- [ ] Phân biệt đúng bác / chú / cô khi có `birth_order`
- [ ] Phân biệt đúng nội / ngoại (chú vs cậu, cô vs dì)
- [ ] Thím / mợ / dượng ra đúng qua cạnh hôn nhân
- [ ] Chênh 3-5 đời ra chắt / chút / chít
- [ ] Thiếu `birth_order` → `confident: false`, **không đoán**
- [ ] Hai người không cùng huyết thống → 200 với `term: null`
- [ ] Toàn bộ test chạy bằng `SimpleTestCase`
- [ ] Endpoint ≤ 2 query

## Risk Assessment
- **Từ xưng hô tiếng Việt khác nhau theo vùng miền.** Bắc gọi "bác" cho cả anh trai bố lẫn chị gái bố; Nam nhiều nơi khác. MVP dùng **chuẩn miền Bắc** (phổ biến nhất trong văn bản gia phả) và ghi rõ trong docs. Tuỳ chọn theo vùng là YAGNI ở MVP.
- **`confident: false` sẽ xuất hiện rất nhiều** với gia phả nhập sơ sài. Đây là tín hiệu tốt để nhắc người dùng bổ sung `birth_order`, không phải lỗi cần giấu.
- **Cám dỗ đoán bừa để trông "thông minh".** Chống lại. Sai vai vế là xúc phạm.
- Bảng ánh xạ dễ phình. Giữ dữ liệu trong `kinship_terms.py` tách khỏi thuật toán để file không vượt 200 dòng.
