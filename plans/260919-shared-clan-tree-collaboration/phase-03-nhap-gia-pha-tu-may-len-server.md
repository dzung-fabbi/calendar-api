---
phase: 3
title: "Nhap gia pha tu may len server"
status: completed
priority: P1
effort: "1.5d"
dependencies: []
---

# Phase 3: Nhập gia phả từ máy lên server

## Overview
Người dùng cũ đang giữ gia phả trong MMKV trên máy (spec `docs/gia-pha-api-spec.md` §1, §12). Một lần `PUT /v1/family/import` đưa toàn bộ snapshot lên, server cấp id mới và trả bảng đổi id để app remap. Là điều kiện để người dùng cũ dùng được phase 4 (liên kết với dòng họ).
Độc lập với phase 1–2 (chỉ đụng `/v1/family`), làm song song được.

## Requirements
- Functional:
  - `PUT /api/gia-pha/v1/family/import`
    ```json
    { "importKey": "uuid do app sinh 1 lần/máy",
      "selfId": "fam_... | null",
      "persons": [ { "id": "fam_...", "name": "...", "gender": "...", "deceased": false,
                     "fatherId": "...", "motherId": "...", "fatherRel": null, "motherRel": null,
                     "spouses": [{ "id": "...", "type": "married" }],
                     "solarBirthDate": "DD-MM-YYYY", "birthTime": "HH:mm", "birthOrder": null,
                     "solarDeathDate": null, "deathTime": null,
                     "lunarDeathDay": 20, "lunarDeathMonth": 12, "lunarDeathYear": null, "lunarLeap": false,
                     "relationship": "Cụ / Tổ tiên", "note": null, "gioEventId": "gio_...",
                     "createdAt": 1690000000000, "updatedAt": 1690000000000 } ] }
    ```
    Response 200:
    ```json
    { "idMap": { "fam_...": "uuid" }, "selfId": "uuid | null",
      "persons": [ "Person..." ],
      "skippedEdges": [ { "code": "PARENT_CYCLE", "personId": "fam_...", "otherId": "fam_...", "message": "..." } ],
      "warnings": [ { "personId": "fam_...", "field": "name", "message": "Tên dài quá 60 ký tự, đã cắt bớt." } ] }
    ```
  - **Chỉ nhận khi gia phả trên server đang trống** (0 người). Có dữ liệu và `importKey` khác → 409 `FAMILY_NOT_EMPTY` ("Tài khoản đã có gia phả trên server. Không nhập đè được."). Không có chế độ ghi đè/gộp (YAGNI; tránh mất dữ liệu).
  - **Idempotent**: gửi lại cùng `importKey` (mạng rớt sau khi server đã ghi) → 200, trả lại đúng `idMap` cũ, không tạo thêm.
  - **Người luôn được nhập, cạnh lỗi thì bỏ**: dữ liệu cũ trên máy không sửa được dễ, nên không từ chối cả lô vì một cạnh.
    - Cạnh cha/mẹ: bỏ khi trỏ người không có trong lô (`DANGLING_*`), tự làm cha/mẹ mình (`SELF_PARENT`), tạo vòng (`PARENT_CYCLE`), sai giới tính ô (nam ở ô mẹ, nữ ở ô cha).
    - Vợ/chồng: gộp hai chiều theo `canonical_pair`; bỏ `SELF_SPOUSE`, `DANGLING_SPOUSE`; `SPOUSE_IS_ANCESTOR` vẫn giữ (chỉ cảnh báo, như §4.1).
    - Thứ tự xét cạnh cố định (theo `createdAt` → `id`) để kết quả tất định.
  - Field: `name` trống → `"Chưa đặt tên"` + warning; quá 60 → cắt + warning; ngày/giờ sai định dạng → null + warning; `lunarDeathDay/Month` ngoài khoảng → null + warning; `relationship` > 24, `note` > 200 → cắt + warning.
  - Giữ nguyên: `gioEventId` (kể cả id `gio_*` cũ, spec §12.3), `createdAt`/`updatedAt` từ client (thứ tự con cháu phụ thuộc `createdAt`).
  - `selfId` trỏ người không có trong lô → null + warning.
  - Chặn > `FAMILY_MAX_PERSONS` (setting đã có) → 400, không ghi gì.
  - Throttle riêng scope `giapha-family-import`: 5/giờ/user.
- Non-functional: một transaction; `bulk_create` người + vợ/chồng, cập nhật cạnh cha/mẹ bằng 1 `bulk_update` → số query cố định, không phụ thuộc số người (test query budget). Body ≤ 500 người × ~1KB.

## Architecture
```
PUT /import ─► serializer (shape, max N) ─► services/family_import.py (thuần)
                                              ├─ normalize fields → warnings
                                              ├─ build graph từ id client
                                              ├─ duyệt cạnh theo thứ tự cố định,
                                              │   kiểm bằng family_rules / family_graph → skippedEdges
                                              └─ trả plan ghi (persons, parent edges, spouse pairs)
                                           ─► selectors/family_import_write.py (atomic, bulk)
```
- Tái dùng luật hiện có (`services/family_rules.py`, `services/family_graph.py`, `services/family_issue.py` cho message tiếng Việt) — không viết lại luật.
- `Family.import_key` (char 36, nullable, unique cùng family) + `FamilyPerson.legacy_id` (char 64, nullable, index) để trả lại `idMap` khi retry và để tra lỗi.
- Sau import, app đổi id local sang id server (`fatherId`/`motherId`/`spouses`/`selfId`), rồi chuyển sang CRUD server; MMKV giữ bản sao lưu tới khi app xác nhận xong (việc của app, ghi trong docs).

## Related Code Files
- Create: `giapha/services/family_import.py`, `giapha/services/family_import_fields.py` (chuẩn hoá field + warnings), `giapha/selectors/family_import_write.py`, `giapha/serializers/family_import.py`, `giapha/views/family_import.py`, `giapha/migrations/0012_family_import_key_legacy_id.py`, tests `test_family_import_service.py`, `test_family_import_api.py`
- Modify: `giapha/models/family.py` (`import_key`, `legacy_id`), `giapha/urls.py`, `djangopj/settings.py` (throttle scope)
- Docs: `docs/gia-pha-api-spec.md` §12 (chốt hợp đồng), `docs/api-reference.md`, `docs/gia-pha-architecture.md` (luồng chuyển MMKV → server)

## Implementation Steps
1. Model fields + migration 0012.
2. `family_import_fields.py`: chuẩn hoá từng field + warnings; unit test bảng giá trị xấu.
3. `family_import.py`: dựng graph, xét cạnh tất định, gom skippedEdges; test fixture: cây sạch, cạnh treo, vòng, sai giới tính ô, vợ chồng một chiều/hai chiều, selfId treo, 500 người.
4. Write selector atomic + bulk; test query budget.
5. View: rỗng/409/idempotent/throttle/capacity.
6. Docs; full suite.

## Success Criteria
- [x] Snapshot 500 người sạch → 200, `idMap` đủ 500, cây `GET /v1/family` giống hệt (cạnh, vợ chồng, selfId, gioEventId, thứ tự con).
- [x] Snapshot có 1 vòng cha–con → mọi người vẫn vào, đúng 1 cạnh bị bỏ, có `skippedEdges`.
- [x] Gửi lại cùng `importKey` → cùng `idMap`, không nhân đôi người.
- [x] Server đã có người, `importKey` khác → 409, không ghi gì.
- [x] Số query không đổi giữa 10 và 500 người.

## Risk Assessment
- Dữ liệu máy cũ có dạng lạ (schema v1 trước migration Giỗ) → app phải chạy migration local v2 trước khi gửi; server chỉ nhận schema v2 (ghi trong docs).
- Bỏ cạnh làm cây vỡ cụm → báo rõ trong `skippedEdges` để app hiện "N quan hệ không nhập được"; không bỏ người.
- Hai máy cùng tài khoản cùng import → máy sau nhận 409; app hướng dẫn chọn máy chính (spec §12 "một device active").
- Chính sách quyền riêng tư: dữ liệu rời khỏi máy lần đầu → app phải hỏi đồng ý trước khi gọi import. **Chủ sản phẩm cập nhật chính sách** (chốt 2026-09-19) — điều kiện trước khi bật import trên production.
- Sau import, mất mạng = chỉ xem (chốt 2026-09-19); không có hàng đợi ghi offline nên server không cần xử lý gộp.
