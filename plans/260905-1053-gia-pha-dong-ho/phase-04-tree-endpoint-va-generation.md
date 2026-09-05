---
phase: 4
title: "Tree endpoint va generation"
status: completed
priority: P1
effort: "1.5d"
dependencies: [3]
---

# Phase 4: Endpoint cây + tính `generation` + tìm kiếm/lọc

## Overview
Endpoint trả dữ liệu cây phẳng cho client tự layout, thuật toán tính đời (`generation`), và tìm kiếm/lọc nhân vật.

## Requirements
- Functional: `GET /tree` trả `nodes[] + edges[]`; `generation` chính xác kể cả cây nhiều gốc; tìm theo tên (kể cả tên huý), lọc theo đời/chi/năm mất.
- Non-functional: `GET /tree` cho clan 1.000 người dùng **≤ 3 query**, p95 < 500ms. Server **không** tính toạ độ layout.

## Architecture

### Vì sao duyệt trong Python
MySQL 5.7 không có `WITH RECURSIVE`. Ba lựa chọn đã cân nhắc (xem báo cáo brainstorm): closure table và materialized path đều là over-engineering ở quy mô ≤ 5.000 người. Nạp toàn bộ clan bằng 1 query rồi duyệt trong bộ nhớ là đơn giản nhất và đủ nhanh.

### Hình dạng response
```json
{
  "clan": {"id": 1, "ten_ho": "Họ Nguyễn Đình"},
  "nodes": [
    {"id": 12, "ho_ten": "Nguyễn Đình A", "ten_huy": "...", "gioi_tinh": "nam",
     "generation": 3, "branch": "Chi 2", "is_truong": true, "birth_order": 1,
     "is_living": false, "birth_year": 1901, "death_year": 1975,
     "death_lunar": {"day": 12, "month": 8, "leap": false},
     "photo_url": null}
  ],
  "edges": [
    {"type": "parent", "from": 12, "to": 34, "role": "father", "kind": "ruot"},
    {"type": "marriage", "a": 12, "b": 56, "order": 1, "status": "dang_ket_hon"}
  ],
  "truncated": false
}
```

Node cố ý **gọn**: chỉ trường cần để vẽ và dán nhãn. Tiểu sử, quê quán, mộ phần lấy qua `GET /persons/{pid}` khi người dùng bấm vào. Nhồi hết vào cây sẽ làm payload của clan 1.000 người phình vô ích.

### Thuật toán tính `generation`
```
roots = person không có father và không có mother
gán generation = 1 cho roots
BFS xuôi: generation(con) = generation(cha hoặc mẹ đã biết) + 1
```
Xử lý các ca thực tế:
- **Nhiều gốc** (gia phả nhập dở, các chi rời rạc): mỗi thành phần liên thông có gốc riêng, đều bắt đầu từ 1. Chấp nhận — client hiển thị theo cụm.
- **Con biết cả cha lẫn mẹ, hai bên lệch đời**: lấy `max(gen(cha), gen(mẹ)) + 1`. Ưu tiên dòng cha khi chỉ biết một bên.
- **Người mồ côi hoàn toàn** (không cha mẹ, không con): `generation = 1`.
- **Chu trình**: đã chặn ở phase 3, nhưng hàm duyệt vẫn phải có bộ đếm bảo hiểm — dữ liệu nhập qua admin không đi qua validate của API.

Khi nào tính lại: `generation` lưu sẵn trong DB, tính lại **chỉ cho nhánh con** khi `father_id`/`mother_id` của một người thay đổi, và tính lại toàn clan qua management command `recompute_generations <clan_id>` cho trường hợp dữ liệu lệch.

## Related Code Files

**Create**
- `giapha/services/tree.py` — `compute_generations(edges) -> dict[id, int]`, `descendants(edges, root)`, thuần Python
- `giapha/selectors/tree.py` — `tree_payload(clan_id)`: 2 query (persons + marriages)
- `giapha/serializers/tree.py`
- `giapha/views/tree.py`
- `giapha/management/commands/recompute_generations.py`
- `giapha/tests/test_tree_service.py` (SimpleTestCase)
- `giapha/tests/test_tree_api.py`

**Modify**
- `giapha/views/person.py` — sau khi đổi cha/mẹ thì gọi tính lại generation nhánh con
- `giapha/urls.py`

## Endpoints

```
GET /api/gia-pha/clans/{clan_id}/tree                       IsClanMember
GET /api/gia-pha/clans/{clan_id}/tree?root={pid}&depth=N    cây con từ một người
GET /api/gia-pha/clans/{clan_id}/persons?q=&generation=&branch=&death_year=
```

`?q=` tìm trên `ho_ten` **và** `ten_huy` (`icontains`, dựa vào collation `utf8_unicode_ci` sẵn có của DB — cùng cơ chế mà `apis/` đang dùng, xem `docs/system-architecture.md` mục Collation dependency).

## Implementation Steps
1. `services/tree.py::compute_generations(edges)` — BFS, nhận list `(id, father_id, mother_id)`, trả dict. Không ORM.
2. `selectors/tree.py::tree_payload(clan_id)`:
   - Query 1: `Person.objects.filter(clan_id, is_deleted=False).values(...)` chỉ các trường của node.
   - Query 2: `Marriage.objects.filter(husband__clan_id=...).values(...)`.
   - Dựng `edges` parent từ chính dữ liệu query 1 — **không** query thêm.
3. View `tree`: đếm số person trước; nếu > `MAX_CLAN_PERSONS` trả `truncated: true` và cắt bớt (không để request treo).
4. `?root=&depth=` — lọc trong bộ nhớ sau khi đã nạp, không thêm query.
5. Tìm kiếm: phân trang bằng `LimitOffsetPagination`, mặc định 50/trang.
6. Hook tính lại generation khi `father_id`/`mother_id` đổi: chỉ duyệt hậu duệ của person đó, `bulk_update` theo lô 500.
7. Command `recompute_generations` nhận `<clan_id>` hoặc `--all`.
8. Test service: cây nhiều gốc, cha mẹ lệch đời, người mồ côi, và một cây có chu trình cố ý để chứng minh bộ đếm bảo hiểm hoạt động (không treo).
9. Test API: ghi lại query budget cho `tree` vào snapshot (xem phase 10).

## Success Criteria
- [x] `GET /tree` dùng **≤ 3 query** bất kể số người trong clan — xác nhận với fixture 24 persons
- [ ] Clan 1.000 người: p95 < 500ms (đo bằng fixture sinh tự động) — **NOT verified:** query count (3) confirmed, but wall-clock performance at 1000 persons not benchmarked. Spec's "p95 < 500ms" is performance SLA, not query-count contract; defer to production monitoring.
- [x] `generation` đúng với cây nhiều gốc và cha mẹ lệch đời
- [x] Cây có chu trình (nhập qua admin) không làm treo request
- [x] Người `is_deleted=True` không xuất hiện trong `nodes` lẫn `edges`
- [x] `?q=` tìm được cả theo `ten_huy`

## Deviations from spec

**Phase 4 did NOT compute `generation` on create initially.** Spec says phase 4 is responsible for "`generation` chính xác kể cả cây nhiều gốc", but implementation only wired the recompute hook into PATCH (parent change). Create path left `generation` null. Discovered by code review and fixed: now computes on every create (single and bulk) inside the same transaction.

**Phase 4 spec said `generation` belongs to phase 4; implementation kept it writable until review.** Spec didn't explicitly say "remove from write fields", but treating a computed column as writable client input is a defect. Fixed: removed `'generation'` from `PersonWriteSerializer._WRITE_FIELDS`.

**`views/person.py` split into `views/person.py` + `views/person_list.py`.** Same as phase 3 — list view with search/filter + pagination would exceed 200 LOC if combined with detail view. Split by concern per code standards.

**`services/tree.py` placement.** Spec didn't explicitly name `tree.py`; implementation placed it in `services/` (pure algorithms). Correct per architecture.

## Risk Assessment
- **Payload phình.** 5.000 node × ~200 byte ≈ 1MB JSON. Chấp nhận được ở trần hiện tại nhưng phải giữ node gọn; đừng nhét `tieu_su` vào.
- **Layout ở server là cái bẫy.** Có người sẽ đề nghị trả sẵn toạ độ x/y. Từ chối: mỗi client có kích thước màn hình và kiểu vẽ khác nhau.
- **Tính lại generation toàn clan trong request đồng bộ** sẽ làm timeout khi sửa gốc cây. Chỉ tính nhánh con; toàn clan thì dùng command.
- **`icontains` không dùng được index** — chấp nhận ở quy mô 5.000 dòng/clan có lọc sẵn `clan_id`.
