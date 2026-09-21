# Brainstorm — Gia phả dùng chung: cá nhân ↔ dòng họ, quyền sửa, mời

Ngày: 2026-09-19 · Trạng thái: **đã duyệt** → lập plan

## Vấn đề
Nhiều người cùng xem/sửa 1 gia phả dòng họ. Cần: phân biệt sửa "thuộc gia đình" vs "thuộc dòng họ", cơ chế mời, và nối gia phả cá nhân (`/v1/family`) với dòng họ (`/clans`).

## Hiện trạng
- `/clans` đã có: role owner/editor/viewer (toàn họ), `ClanInvite` (code, role, hạn, lượt), `ClanMember.person` (toi-la, **tự nhận, không xác minh**), `PersonRevision` + restore, `GioFollow`, public link, xưng hô.
- `/v1/family`: 1 user = 1 cây, schema riêng (`male/female/unknown`, ngày chuỗi `DD-MM-YYYY`, `lunarDeathYear`, `relationship` = nhãn với "tôi").
- Thiếu: quyền theo phạm vi gia đình; đề xuất/duyệt; liên thông 2 cây.

## Quyết định người dùng
- Hai cây (cá nhân + họ) — lý do đúng: 1 người thuộc nhiều họ (nội, ngoại, nhà vợ); cây cá nhân = góc nhìn xuyên họ + ghi chú riêng.
- Sửa: nhánh mình trực tiếp + đề xuất cho phần còn lại.
- Quy mô: từ gia đình (~200) lớn dần thành dòng họ (nghìn, nhiều chi).

## Phương án đã xét
| Phương án | Ưu | Nhược |
|---|---|---|
| A. Gộp làm một (cá nhân = họ 1 thành viên) | 1 nguồn sự thật | Mất góc nhìn đa họ; refactor `/v1/family` vừa ship |
| B. Chuyển 1 lần (move) | Đơn giản | Không đa họ; app 2 luồng UI |
| C. Hai cây + đồng bộ 2 chiều thật | Linh hoạt | Merge/xung đột/trùng người — rủi ro cao, bug khó tái hiện. **Không khuyến nghị** |
| **D. Liên kết tham chiếu, không đồng bộ** | Giữ đa họ + riêng tư; mỗi field 1 nguồn | Cần module ánh xạ schema; UX ghép cần xác nhận |

## Giải pháp chốt: D

### 1. Link thay đồng bộ
- Bảng `FamilyPersonLink(family_person, clan, clan_person, linked_by, created_at)`; unique `(family_person, clan)` và `(family, clan_person)`. 1 node cá nhân → tối đa 1 node mỗi họ, nhiều họ được.
- Node đã link **đọc thẳng field chung từ họ**: tên, giới tính, đã mất, ngày sinh, ngày mất âm (+ năm, nhuận). Ảnh chỉ ở họ (cây cá nhân không có ảnh). Không copy → không sync.
- Field riêng giữ ở cá nhân: `relationship`, `note`, `gioEventId`.
- "Tách" (unlink): chép snapshot field chung về cá nhân, sau đó độc lập.
- Cấu trúc (cha/mẹ/vợ chồng) mỗi cây giữ riêng; lệch → endpoint báo khác biệt, không tự sửa.
- Rời họ / bị xoá khỏi họ → link tự tách (snapshot) để cây cá nhân không mất dữ liệu.

### 2. Luồng (luôn do user bấm)
- **Tạo họ từ cây của tôi**: chọn cụ tổ → chép hậu duệ (+ vợ/chồng) thành clan mới; tạo link; user = owner, binding verified.
- **Ghép với cây của tôi** (sau khi join): server gợi ý cặp (tên chuẩn hoá bỏ dấu + năm sinh + vị trí tương đối với binding); user xác nhận **từng cặp**. Chưa có bên mình → "Nhận về" (import + link). Chưa có bên họ → "Đóng góp" (đề xuất tạo).
- **Sửa node đã link**: có quyền trên clan_person → ghi thẳng họ (kiểm `version`, 409 nếu lệch); không → tạo ChangeRequest.

### 3. Quyền
- Giữ owner/editor/viewer. Thêm **phạm vi gia đình** từ binding đã xác minh: bản thân, vợ/chồng, cha mẹ, con cháu + vợ/chồng của con cháu → member sửa/thêm trực tiếp.
- Ngoài phạm vi → `ChangeRequest(clan, person?, action, payload_json, base_version, proposer, status: pending|approved|rejected|stale, reviewer, review_note)`. Duyệt = áp qua service hiện có + ghi `PersonRevision`. Push FCM cho người duyệt đúng phạm vi.
- **Editor theo chi**: `ClanMember.scope_root_person` (null = toàn họ); quyền = hậu duệ của gốc. Kiểm bằng cây nạp in-memory (đã có, ≤5000).
- **Bịt lỗ**: `ClanMember.person_verified`. Nhận qua lời mời gắn người → verified; tự nhận → chờ editor duyệt. Chưa verified vẫn nhận nhắc giỗ, không có quyền sửa.

### 4. Mời
- `ClanInvite.person` (nullable): mời đúng vị trí → join tự bind + verified. Chặn nếu node đã có người nhận.
- Deep link + QR (share Zalo).
- **Chốt (2026-09-19)**: con cháu đã xác minh tự mời được. Người trong phạm vi gia đình + quyền thành viên → mã có ngay. Vượt cấp gia đình, không gắn người, hoặc quyền editor → **trưởng họ (owner) duyệt**; lời mời chờ duyệt chưa có mã.
- **Chốt (2026-09-19)**: thêm role `manager` (Ban quản lý) = editor toàn họ + duyệt lời mời (role viewer), xác minh binding, duyệt đề xuất thay trưởng họ. Không đổi role, không cấp editor, không đụng cài đặt họ.

## Thứ tự triển khai
1. Phạm vi gia đình + `person_verified` + lời mời gắn người (chỉ `/clans`, giá trị cao nhất, độc lập).
2. ChangeRequest + duyệt + push.
3. Import gia phả từ máy lên server (`PUT /v1/family/import`) — người dùng cũ cần trước bước 4.
4. Link cá nhân↔họ: tạo họ từ cây, ghép/gợi ý, đọc thẳng, tách.
5. Sửa node link đi vào họ + `version` optimistic lock (Person clan).
6. Editor theo chi.

## Rủi ro
- Lệch schema 2 model → 1 module ánh xạ duy nhất (`family_clan_field_map`), test round-trip.
- Ghép nhầm → không bao giờ auto-link; luôn xác nhận.
- Soft-delete clan Person (clan) vs hard-delete FamilyPerson → link trỏ node đã xoá mềm = coi như tách.
- Quyền phạm vi gia đình phụ thuộc tính đúng quan hệ in-memory → test ma trận quyền mở rộng (`test_permissions.py`).
- UX người lớn tuổi: cây cá nhân tuỳ chọn; người chỉ dùng họ không thấy khái niệm link.
- Chính sách quyền riêng tư: dữ liệu cá nhân lên server + chia sẻ trong họ → cập nhật policy.

## Tiêu chí thành công
- Member verified sửa được con mình không cần editor; sửa cụ tổ → tạo đề xuất.
- Tự nhận "tôi là X" không đem lại quyền sửa trước khi duyệt.
- Sửa tên cụ trong họ → cây cá nhân của mọi người đã link thấy ngay, không job sync.
- Tách link → cây cá nhân giữ nguyên giá trị cuối.
- Không endpoint nào ghi tự động từ cây cá nhân sang họ khi user không bấm.

## Đã chốt sau duyệt (2026-09-19)
- Anh chị em ruột: trong phạm vi gia đình chỉ khi chưa vào app/chưa xác minh.
- Đề xuất: nhắc ngày 7, hết hạn ngày 30.
- Xác minh tự nhận: trưởng họ, Ban quản lý, trưởng chi của chi chứa node.
- Ghép theo tên: phải trùng năm sinh.
- Thêm cờ `da_mat` cho clan Person.

## Câu hỏi còn mở
- (hết) Import từ máy: **chốt có**, thành phase 3.
