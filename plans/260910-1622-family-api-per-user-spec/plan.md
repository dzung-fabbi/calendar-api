# Family API (one user = one gia phả) — theo `gia-pha-api-spec.md`

**Ngày:** 2026-09-10 · **Trạng thái:** ✅ Done (944 tests OK, chưa commit) · **Nhánh:** master

## Bối cảnh
- App mobile (RN) lưu gia phả local MMKV, chưa có API. Spec `gia-pha-api-spec.md` mô tả hợp đồng
  BE khớp logic app: Person chỉ lưu cạnh đi lên + spouses, selfId scalar, mutation quan hệ từng lệnh,
  xoá không lan, mã lỗi `IssueCode` + message vi.
- `giapha/` hiện có mô hình **clan đa người dùng** (26 endpoint, `Person` int id, `Marriage`
  husband/wife, xoá mềm, revision, generation). Ngữ nghĩa xung đột với spec (xoá mềm bị chặn khi
  còn con vs xoá cứng không lan; hôn nhân gendered vs `unknown`; không có `deceased`; id int vs UUID).

## Quyết định
- **Giữ nguyên** API clan. **Thêm** surface mới `/api/gia-pha/v1/family/...` với 3 bảng riêng
  (`giapha_family`, `giapha_familyperson`, `giapha_familyspouse`) đúng mục 11 spec.
- Tái dùng: `services.person_rules.descendants` (cycle), `services.vn_lunar.lunar_to_solar`
  (suy ngày dương từ âm), `exceptions.py` pattern.
- Response **phẳng** theo spec (không bao `{"data"}`), lỗi `{ok:false, error:{code,message,...}}`.
- Auth: `IsAuthenticated`; Family tự tạo (`get_or_create`) theo user.
- Bổ sung sau review: cap `FAMILY_MAX_PERSONS` (settings, 1000) → `FAMILY_FULL`; warning `OTHER_PARENT_NOT_CANDIDATE`; test cách ly cross-user (`test_family_isolation_api.py`); query budget (`test_family_query_counts.py`).
- Không làm: `PUT /import` (spec mục 12 ghi ngoài phạm vi), events server-side, candidates endpoint.

## Phases
| # | Phase | File | Status |
|---|---|---|---|
| 1 | Models + migration 0009 | [phase-01](phase-01-models-migration.md) | ✅ |
| 2 | Pure services: graph index, rules, IssueCode, serialize | [phase-02](phase-02-graph-rules-services.md) | ✅ |
| 3 | Selectors (load/write) + serializers (draft in / dict out) | [phase-03](phase-03-selectors-serializers.md) | ✅ |
| 4 | Views + urls (13 endpoint) | [phase-04](phase-04-views-urls.md) | ✅ |
| 5 | Tests (SimpleTestCase rules + API TestCase) | [phase-05](phase-05-tests.md) | ✅ |
| 6 | Docs: api-reference, system-architecture, codebase-summary | [phase-06](phase-06-docs.md) | ✅ |

## Endpoint
```
GET    v1/family                         {selfId, persons[]}
GET    v1/family/persons/{id}            {person}
POST   v1/family/persons                 draft → 201 {ok, person, persons, linked, hint}
PATCH  v1/family/persons/{id}            draft (partial) → {ok, person}
DELETE v1/family/persons/{id}            {deleted, detachedFrom[], selfId}
PUT    v1/family/self                    {personId|null} → {selfId}
PUT    v1/family/persons/{id}/gio-event  {eventId|null} → {ok, person}
POST   v1/family/relations/add-relative | set-parent | link-spouse | unlink-spouse | link-child
```
