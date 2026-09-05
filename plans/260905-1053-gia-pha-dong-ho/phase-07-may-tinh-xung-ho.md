---
phase: 7
title: "May tinh xung ho"
status: completed
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
- Non-functional: `services/kinship.py` thuần Python, `SimpleTestCase`; endpoint ≤ 2 query *(đã ship 2–4 — xem Success Criteria)*.

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

*(bảng dưới là **thực tế đã ship**; plan gốc dự kiến 2 service module + dùng lại `clan_edges` — xem "Làm khác plan")*

**Created**
- `giapha/services/kinship.py` (75) — `resolve_kinship`: máu mủ → hôn nhân → không liên kết; + pipeline map
- `giapha/services/kinship_blood.py` (77) — hình dạng response (`result`/`unrelated`/`blood_result`)
- `giapha/services/kinship_graph.py` (107) — `ancestor_index`, `best_common_ancestor`, `lowest_common_ancestor`
- `giapha/services/kinship_lookup.py` (126) — facts → từ; **một** generator `_candidate_keys` cho cả `TERMS` và `AMBIGUOUS_TERMS`
- `giapha/services/kinship_terms.py` (197) — từ vựng máu mủ + hedge + `REASON_*` slug + `REASON_LABELS` (dữ liệu thuần)
- `giapha/services/kinship_affinal.py` (194) — toàn bộ nửa hôn nhân, cả hai chiều
- `giapha/services/kinship_affinal_terms.py` (109) — `AFFINAL_TERMS`/`SPOUSE_TERMS`/`MARRIED_IN_SUBSTITUTES`
- `giapha/services/kinship_marriage_rows.py` (68) — luật xếp hạng hôn nhân (N1), không import gì
- `giapha/serializers/kinship.py` (83), `giapha/views/kinship.py` (106)
- `giapha/tests/test_kinship.py` (686), `test_kinship_reciprocity.py` (373), `test_kinship_api.py` (210)

**Modified**
- `giapha/selectors/person.py` — **thêm** `clan_kinship_rows` (insertion thuần; `clan_edges` không đổi)
- `giapha/selectors/marriage.py` — thêm `clan_spouse_pairs` (mang `status`/`order`)
- `giapha/urls.py`, 3 file `__init__.py` re-export

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
- [x] Phân biệt đúng bác / chú / cô khi có `birth_order`
- [x] Phân biệt đúng nội / ngoại (chú vs cậu, cô vs dì) — theo **chuẩn Bắc nghiêm** (xem "Quyết định chủ dự án")
- [x] Thím / mợ / dượng ra đúng qua cạnh hôn nhân
- [x] Chênh 3-5 đời ra chắt / chút / chít — trực hệ đúng như spec; **thang bàng hệ lệch một bậc so với spec** (gap 2 → `cháu`, 3 → `chắt`, 4 → `chút`, 5 → `chít`) để đối ứng thang lên `bác/ông/cụ/kỵ`. Spec ghi "chênh 3 đời → chắt" — vẫn đúng.
- [x] Thiếu `birth_order` → `confident: false`, **không đoán**
- [x] Hai người không cùng huyết thống → 200 với `term: null`
- [x] Toàn bộ test chạy bằng `SimpleTestCase` (3 module kinship, không DB)
- [ ] ~~Endpoint ≤ 2 query~~ — **KHÔNG ĐẠT. Thực tế 2–4 query**, đã đo và ghim bằng test:

  | Trường hợp | Query |
  |---|---|
  | `a` truyền tường minh + có quan hệ máu mủ | **2** |
  | `a` mặc định (đọc `ClanMember.person` binding) | **3** |
  | `a` tường minh, không có liên kết máu mủ (nạp thêm `Marriage`) | **3** |
  | `a` mặc định + không máu mủ (role + binding + rows + marriages) | **4** (xấu nhất) |

  Hai `+1` đều có lý: binding lookup không tránh được khi `a` bị bỏ trống (tính năng phát sinh sau spec, từ phase 6); nạp `Marriage` là **lazy** — chỉ khi lượt đi máu mủ thất bại — chính cái lazy đó giữ ca phổ biến ở 2 query. Trần 4 nay ghi trong docstring của view và ghim bởi `test_worst_case_is_four_queries`. Reviewer chấp nhận cả hai nhưng gọi đúng tên: budget creep.

## Đã ship (2026-09-05)

**Suite 470 → 579 passed / 4 skipped.** `makemigrations giapha --check --dry-run` sạch. **Không thêm model, không thêm migration.** Không chạm `apis/`.

Đường đi: implement → review (2 Critical, 4 High, 5 Med, 5 Low, 6/10, **NOT SHIPPABLE**) → fix → verify (8/10, SHIPPABLE, 1 High mới = N1) → fix lần hai → xong.

Báo cáo: [implement](../reports/fullstack-260905-1918-phase-07-kinship.md) · [review 1](../reports/code-reviewer-260905-2016-phase-07-kinship.md) · [fix 1](../reports/fullstack-260905-2029-phase-07-review-fixes.md) · [verify](../reports/code-reviewer-260905-2054-phase-07-fix-verification.md) · [fix 2](../reports/fullstack-260905-2110-phase-07-final-fixes.md)

### Làm khác plan

| Plan nói | Thực tế | Lý do |
|---|---|---|
| Bước 1: **mở rộng `clan_edges`** thêm `birth_order`/`gioi_tinh` | **KHÔNG mở rộng.** Selector mới `clan_kinship_rows` (trả **dict**, 1 query) mang `birth_order`/`gioi_tinh`/`ho_ten` | `clan_edges` đã có consumer ở phase 4 và 6 unpack 3-tuple; nới là phá cả hai. Dict thêm khoá được mà không sửa consumer. `clan_edges`/`clan_edges_all` **nguyên vẹn** (git diff `person.py` là một insertion thuần) |
| — | `clan_spouse_pairs` thêm vào **`selectors/marriage.py`** (không phải `person.py`), mang `status`/`order` | Nó query `Marriage`; nhét vào `person.py` là phá biên module. Loại `ly_hon`, giữ `goa` |
| Bảng khoá `(da, db, side, gender, elder)` | Khoá **`(kind, gap, side, gender, elder)`** | Cặp độ sâu **không collapse**: em họ của bố `(3,2)` và chú `(2,1)` là **cùng một từ**. Khoá theo cặp thô cần bảng vô hạn. `kind` = trực hệ vs bàng hệ — chính nó tách `con/cháu` khỏi `cháu/chắt` |
| 2 service module | **8 module** (`kinship`, `_blood`, `_affinal`, `_affinal_terms`, `_graph`, `_lookup`, `_terms`, `_explain`, `_marriage_rows`) | Luật 200 dòng. Hai lần buộc tách giữa đường: `kinship.py` chạm 271 dòng, `kinship_affinal.py` chạm 241. Không có cycle, mỗi file một concern |
| `a` bắt buộc | **`a` tuỳ chọn**, mặc định = binding `ClanMember.person` của caller (phase 6) | Người hỏi "tôi gọi người này là gì" thường là chính caller. Chưa bind → 400 chỉ sang `/toi-la`; binding trỏ vào node xoá mềm → message riêng |
| Bước 5: chỉ chiều **B** kết hôn | **Cả hai chiều** (A-side affinity) | Con dâu mới về không có liên kết máu mủ nào → mọi câu hỏi trả "không cùng huyết thống". Mà con dâu mới về **chính là** người dùng số một của tính năng này. Một implementation, gọi hai lần đảo tham số |

### Quyết định chủ dự án

1. **Chuẩn miền Bắc nghiêm.** Anh/chị của **cả cha lẫn mẹ** → `bác` (bất kể giới tính của người đó). `chú`/`cô` chỉ dành cho em của **cha**; `cậu`/`dì` chỉ cho em của **mẹ**. Bảng ban đầu cho bên ngoại `elder=None` (mọi anh em của mẹ đều `cậu`/`dì`) — mâu thuẫn với docstring của chính file nó, và là **đúng một chỗ** từ có vai vế trả `confident: true` mà không có `birth_order` chống lưng. Đã sửa bảng, không sửa docstring. Hệ quả đúng: bên ngoại nay cũng đòi `birth_order` như bên nội (hedge `bác/cậu`, `bác/dì`, `bác/cậu/dì`).
2. **A-side affinity làm ngay**, không hoãn sang phase sau.

### Defect đáng ghi (đã fix, đều có regression test đỏ-trước-xanh-sau)

| # | Lỗi | Vì sao đáng ghi |
|---|---|---|
| C1 | **Thang bàng hệ đi xuống lệch một bậc** — cháu của anh trai bạn nhận `chắt`, gọi lại bạn là `ông`. `ông ↔ chắt` **không phải một cặp**. `confident: true`. | File **tự mâu thuẫn với block `TRUC` của chính nó**, vốn ghi đúng. Hai test hiện có *ghim* cái sai; cùng đọc chéo là thấy, không ai đọc. Đúng cái "sai vai vế" plan cấm |
| C2 | **Vợ ruột của mình trả về `chị`**, `confident: true` | Self-check nằm *trong* vòng lặp spouse. B có 2 hôn nhân không ly hôn, partner kia id nhỏ hơn → nhánh máu mủ thắng trước. Câu trả lời phụ thuộc **thứ tự autoincrement** |
| H1 | Anh em thiếu `birth_order` **mất hẳn hedge**, rò slug ASCII vào câu tiếng Việt | Hedge tra bảng bằng `side` thật, còn 3 hàng `gap == 0` lại khoá `side=None` → **dead code không đời nào chạm tới**. Gốc: `_candidate_keys` đã nới `side` sẵn, người viết tự tay viết fallback thứ hai. DRY vi phạm có hậu quả correctness |
| H3 | "Không cùng huyết thống", `confident: true`, trả cho người **rõ ràng là dâu/rể** | Không có từ ≠ không có quan hệ. Nay `khong_co_tu_xung_ho_thong_dung` + `confident: false` + `explain` nêu tên người trung gian |
| N1 | **Đi qua vợ/chồng nào là do id autoincrement quyết định** — cùng kiểu lỗi C2, chưa chết hẳn | `clan_spouse_pairs` bỏ mất `status`/`order` nên service **không có cách nào** ưu tiên hôn nhân đang sống. Ca tái hôn sau khi chồng mất (levirate) cho ra `anh`/`em` sai tự tin: vợ của em được bảo gọi anh chồng là `em`. Phase 6/H4 còn nhân đôi nó sang bên A. Nay: non-`goa` > `goa`, `order` nhỏ thắng, id **chỉ** là tie-break; ngang rank mà khác từ → hedge |

### Chốt an toàn hiện có

**Test property đối ứng** (`giapha/tests/test_kinship_reciprocity.py`) — bảng `RECIPROCAL` **viết tay, độc lập với `TERMS`**, nên không phải lặp lại thứ đang kiểm. Quét mọi cặp có thứ tự trên một clan dựng riêng (5 đời lên, 6 đời xuống, cả nội và ngoại, một nhánh bàng hệ sâu 6).

**Đã mutation-verify** (áp mutation, chạy, revert, `diff` byte): revert C1 → đỏ (`132 gọi 107 là "ông" nhưng 107 gọi lại là "chắt"`); thêm hàng `TERMS` không ai chạm → đỏ; lật `bác`→`cậu` (tái phát H2) → đỏ. Lần verify đầu, cú lật H2 này để file **xanh hoàn toàn** — nên đã thêm ba lớp nữa: `BY_HAND` (18 cặp ghim *từ nào* ở gap 0/1, chỗ `RECIPROCAL` mù vì mọi thứ đều đối ứng `cháu`), fixture thứ hai *cố tình thiếu field* để sinh hedge + quét đối ứng cho hedge, và `RULED_OUT_BY` (không cần bảng: B gọi A là `em` tự tin thì hedge của A không được còn chào `em`).

### Ranh giới của chốt đó (ghi để đời sau không tin quá)

Sweep ràng buộc **độ sâu thang**, không ràng buộc **chọn từ ở gap 0/1** — chỗ đó do `BY_HAND` giữ, mới hơn. Sweep hedge cũng mới, ít trận mạc hơn sweep từ máu mủ.

## Risk Assessment
- **Từ xưng hô tiếng Việt khác nhau theo vùng miền.** Bắc gọi "bác" cho cả anh trai bố lẫn chị gái bố; Nam nhiều nơi khác. MVP dùng **chuẩn miền Bắc** (phổ biến nhất trong văn bản gia phả) và ghi rõ trong docs. Tuỳ chọn theo vùng là YAGNI ở MVP.
- **`confident: false` sẽ xuất hiện rất nhiều** với gia phả nhập sơ sài. Đây là tín hiệu tốt để nhắc người dùng bổ sung `birth_order`, không phải lỗi cần giấu.
- **Cám dỗ đoán bừa để trông "thông minh".** Chống lại. Sai vai vế là xúc phạm.
- Bảng ánh xạ dễ phình. Giữ dữ liệu trong `kinship_terms.py` tách khỏi thuật toán để file không vượt 200 dòng.
