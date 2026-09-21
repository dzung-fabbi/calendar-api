---
phase: 4
title: "Lien ket ca nhan voi dong ho"
status: completed
priority: P2
effort: "4d"
dependencies: [1, 2, 3]
---

# Phase 4: Liên kết cá nhân với dòng họ

## Overview
Node trong gia phả cá nhân liên kết tới node trong một hoặc nhiều dòng họ. Node đã liên kết đọc field chung từ họ (một nguồn, không đồng bộ). Có luồng tạo họ từ cây, ghép gợi ý, nhận về, đóng góp, tách.

## Requirements
- Functional:
  - Model `FamilyPersonLink(family, family_person CASCADE, clan CASCADE, clan_person CASCADE, linked_by, created_at)`; unique `(family_person, clan)` và `(family, clan_person)`.
  - Field chung (overlay khi đọc): name, gender, deceased, solarBirthDate, solarDeathDate, lunarDeath{Day,Month,Year}, lunarLeap. Field riêng giữ ở cá nhân: relationship, note, gioEventId, birthTime, deathTime.
  - Link chỉ khi user là member của họ; clan_person không xoá mềm.
  - Gia phả cá nhân phải ở trên server: người dùng cũ chạy import (phase 3) trước; `GET /links/suggestions` trên gia phả trống trả gợi ý import.
  - Endpoints (`/api/gia-pha/v1/family/...`):
    - `GET /v1/family` thêm `links: [{id, personId, clanId, clanPersonId, clanName}]`; person đã link trả field chung đã overlay + `linked: true`.
    - `POST /v1/family/clans` `{rootPersonId, tenHo, thuyTo?}` (khác `POST /clans` hiện có: tạo họ trống): chép root + hậu duệ + vợ/chồng hậu duệ thành clan Person + Marriage, link tất cả, caller = owner, binding = bản chép của selfId (verified) nếu self nằm trong nhánh. Atomic, chặn > `MAX_CLAN_PERSONS`.
    - `GET /links/suggestions?clanId=`: cặp gợi ý + `confidence` + `reason`.
    - `POST /links` `{clanId, pairs: [{personId, clanPersonId}]}` (xác nhận, max 200).
    - `DELETE /links/{id}`: tách — ghi field chung hiện tại của họ vào FamilyPerson rồi xoá link.
    - `POST /links/import` `{clanId, clanPersonIds[]}`: tạo FamilyPerson + link; nối cạnh cha/mẹ/vợ chồng giữa các người đã link/đã import qua `family_rules` (vi phạm → bỏ cạnh, trả `skippedEdges`).
    - `POST /links/contribute` `{personId, clanId, fatherClanPersonId?, motherClanPersonId?}`: trong phạm vi → tạo thẳng + link; ngoài → ChangeRequest `create_person` mang `family_person_id`, approve thì tự link.
    - `GET /links/diff?clanId=`: các cặp đã link có cha/mẹ/vợ chồng lệch nhau.
  - Rời họ / bị xoá khỏi họ / họ xoá mềm / clan_person xoá mềm → tách tự động (snapshot) cho user đó.
- Non-functional: `GET /v1/family` tối đa +2 query (links, clan persons bulk). Ghép gợi ý chạy in-memory, < 300ms với 5000 × 500.

## Architecture
- `services/family_clan_field_map.py`: `clan_to_family(person) -> dict`, `family_to_clan(draft) -> dict`. `nam/nu/khac ↔ male/female/unknown`; Date ↔ `DD-MM-YYYY`; lunarDeathYear suy từ `death_solar` qua `vn_lunar`. Round-trip test.
- Clan Person chưa có cờ đã mất tường minh → thêm `Person.da_mat` (migration + data migration từ dấu mất hiện có; cập nhật `_is_deceased`, public tree, gio). **Đã chốt** 2026-09-19: thêm.
- `services/family_clan_matching.py`: 
  1. Neo: cặp (selfId ↔ binding của user trong họ) nếu có.
  2. Lan theo cấu trúc từ neo: cha↔cha, mẹ↔mẹ, vợ/chồng, con khớp tên chuẩn hoá → confidence cao.
  3. Còn lại: tên bỏ dấu lowercase + **năm sinh trùng khớp** (chốt; hai bên đều phải có năm) → confidence thấp. Thiếu năm → không gợi ý theo tên, chỉ gợi ý theo cấu trúc.
  Không bao giờ tự link.
- `services/family_clan_bootstrap.py` (tạo họ từ cây), `services/family_link_detach.py`.
- Hook tách: trong view xoá member, rời họ, xoá mềm họ/person.

## Related Code Files
- Create: `giapha/models/family_link.py`, `giapha/migrations/0013_family_person_link_da_mat.py`, `giapha/services/family_clan_field_map.py`, `giapha/services/family_clan_matching.py`, `giapha/services/family_clan_bootstrap.py`, `giapha/services/family_link_detach.py`, `giapha/selectors/family_link.py`, `giapha/serializers/family_link.py`, `giapha/views/family_link.py`, `giapha/views/family_link_flow_clan.py`, tests `test_family_clan_field_map.py`, `test_family_clan_matching.py`, `test_family_link_api.py`, `test_family_clan_bootstrap.py`
- Modify: `giapha/models/person.py` (`da_mat`), `giapha/selectors/family.py`, `giapha/serializers/family_output.py` (overlay), `giapha/views/clan_membership.py`, `giapha/views/clan.py`, `giapha/views/person.py` (hook tách), `giapha/services/change_request_apply.py` (link khi approve contribute), `giapha/urls.py`
- Docs: `docs/gia-pha-api-spec.md` (mục mới "Liên kết dòng họ"), `docs/api-reference.md`, `docs/gia-pha-architecture.md`, chính sách quyền riêng tư (ghi chú cho app)

## Implementation Steps
1. Field map + `da_mat` + round-trip test.
2. Model link + overlay trong `GET /v1/family` (+ query budget test).
3. Bootstrap tạo họ từ cây.
4. Matching thuần + test fixture hai cây lệch.
5. Confirm link, import, contribute, diff, detach.
6. Hook tách tự động; docs; full suite.

## Success Criteria
- [x] Sửa tên cụ trong họ → `GET /v1/family` của mọi user đã link thấy ngay.
- [x] Tách → FamilyPerson giữ giá trị cuối từ họ.
- [x] Bị xoá khỏi họ → link của user đó tự tách, cây cá nhân không mất dữ liệu.
- [x] Không endpoint nào ghi sang họ khi user không gọi trực tiếp.
- [x] Gợi ý không bao giờ tạo link.

## Risk Assessment
- Lệch schema → một module map duy nhất, test round-trip mọi field.
- Ghép nhầm (trùng tên phổ biến "Nguyễn Văn Hùng") → neo cấu trúc trước, name-only luôn low confidence.
- `da_mat` đụng public tree / gio / binding → chạy lại test phase 5-9 cũ.
- Hard-delete clan Person (admin) → link cascade, cá nhân rơi về giá trị lưu cũ; ghi trong docs.

## Deviations
- `GET /v1/family` costs +1 query (not +2). Person linked into multiple clans reads from OLDEST link. Public page liveness unchanged (still date-based, fail-closed); `da_mat` used by member API, tree `is_living`, and binding logic.
