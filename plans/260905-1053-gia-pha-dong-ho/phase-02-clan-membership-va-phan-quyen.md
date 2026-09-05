---
phase: 2
title: "Clan membership va phan quyen"
status: completed
priority: P1
effort: "1d"
dependencies: [1]
---

# Phase 2: Clan / ClanMember / Invite + phân quyền

## Overview
API tạo và quản trị dòng họ, mời thành viên bằng mã, và lớp phân quyền dùng chung cho mọi endpoint về sau.

## Requirements
- Functional: tạo họ (người tạo thành `owner`), sinh mã mời, tham gia bằng mã, liệt kê/đổi vai trò/gỡ thành viên.
- Non-functional: mọi endpoint phía sau **bắt buộc** đi qua cùng một lớp permission — không viết lại kiểm tra quyền ở từng view.

## Architecture

### Ma trận quyền
| Hành động | owner | editor | viewer |
|---|---|---|---|
| Xem cây, hồ sơ, lịch giỗ | ✅ | ✅ | ✅ |
| Thêm/sửa/xoá Person, Marriage | ✅ | ✅ | ❌ |
| Sinh mã mời | ✅ | ❌ | ❌ |
| Đổi vai trò, gỡ thành viên | ✅ | ❌ | ❌ |
| Đổi `visibility`, xoá dòng họ | ✅ | ❌ | ❌ |

Không có "duyệt sửa" (approval queue) trong MVP — YAGNI; `PersonRevision` + quyền editor đã đủ để hoàn tác.

### Permission classes
`giapha/permissions.py`:
- `IsClanMember` — có `ClanMember` cho `clan_id` trong URL
- `IsClanEditor` — role ∈ {owner, editor}
- `IsClanOwner` — role == owner

Cả ba lấy `clan_id` từ `view.kwargs['clan_id']` và **cache role trong `request` sau lần truy vấn đầu**, để không tốn 1 query mỗi lần check trong cùng request.

### Sinh mã mời
`code` = 8 ký tự từ bộ chữ không nhập nhằng `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` (bỏ `0/O`, `1/I`), lấy từ `secrets.choice`. Retry khi trùng (unique constraint).

## Related Code Files

**Create**
- `giapha/permissions.py`
- `giapha/services/invite_code.py` — sinh mã, thuần Python, không ORM
- `giapha/selectors/clan.py` — `clan_role_for(user, clan_id)`, `members_of(clan_id)`
- `giapha/serializers/clan.py` — `ClanSerializer`, `ClanMemberSerializer`, `ClanInviteSerializer`
- `giapha/views/clan.py`
- `giapha/tests/factories.py` — builder tạo clan + user các vai trò (dùng lại xuyên suốt các phase)
- `giapha/tests/test_permissions.py`

**Modify**
- `giapha/urls.py`

## Endpoints

```
POST   /api/gia-pha/clans                    tạo họ            auth
GET    /api/gia-pha/clans                    họ mà tôi thuộc   auth
GET    /api/gia-pha/clans/{clan_id}          IsClanMember
PATCH  /api/gia-pha/clans/{clan_id}          IsClanOwner
DELETE /api/gia-pha/clans/{clan_id}          IsClanOwner (soft delete)
GET    /api/gia-pha/clans/{clan_id}/members  IsClanMember
PATCH  /api/gia-pha/clans/{clan_id}/members/{user_id}   IsClanOwner (đổi role)
DELETE /api/gia-pha/clans/{clan_id}/members/{user_id}   IsClanOwner
POST   /api/gia-pha/clans/{clan_id}/invites  IsClanOwner  -> {code, expires_at}
POST   /api/gia-pha/join                     auth, body {code}
```

## Implementation Steps
1. Viết `services/invite_code.py`: `generate_code(length=8)` + `is_expired(invite, now)`. Không ORM → test bằng `SimpleTestCase`.
2. Viết `selectors/clan.py`. `clan_role_for` trả `None` nếu không phải thành viên — view phân biệt 404 (không phải thành viên, **không** tiết lộ clan tồn tại) với 403 (là thành viên nhưng thiếu quyền).
3. Viết `permissions.py` với cache role trên `request._giapha_role_cache` (dict theo clan_id).
4. Viết serializers. `ClanSerializer` **không** expose `public_slug` cho `viewer` — chỉ owner thấy.
5. Viết views. `POST /clans` bọc trong `transaction.atomic`: tạo `Clan` + `ClanMember(role='owner')` cùng lúc.
6. `POST /join`: khoá hàng invite bằng `select_for_update()` rồi tăng `used_count` — chống dùng vượt `max_uses` khi gọi song song. Nếu đã là thành viên → 200 idempotent, không tạo bản ghi thứ hai.
7. Chặn hạ vai trò owner cuối cùng: nếu clan chỉ còn 1 owner, `PATCH`/`DELETE` lên owner đó trả 400.
8. Viết `tests/factories.py`: `build_clan_fixture()` trả clan + 4 user (owner, editor, viewer, outsider) đã gắn sẵn.
9. Viết `tests/test_permissions.py` phủ toàn bộ ma trận quyền ở trên, gồm cả outsider nhận 404 chứ không phải 403.

## Success Criteria
- [x] Toàn bộ ô trong ma trận quyền có test tương ứng
- [x] Outsider gọi `GET /clans/{id}` nhận **404**, không phải 403 (không rò sự tồn tại của clan)
- [x] Mã mời hết hạn / vượt `max_uses` bị từ chối — **lưu ý:** phase này chưa bật default expiry 30 ngày, chỉ đối xử `None` = unlimited
- [x] Gọi `/join` hai lần bằng cùng mã không tạo 2 `ClanMember`
- [x] Không thể hạ cấp/gỡ owner cuối cùng
- [x] Kiểm tra quyền tốn ≤ 1 query mỗi request

## Deviations from spec

**`Clan.is_deleted` added in phase 2 (not phase 1).** Phase 1 spec didn't mention soft-delete; during phase 2 implementation, it became clear that membership/permissions API needed soft-delete semantics (`clan_role_for` must 404 for deleted clans). Added `Clan.is_deleted` here with migration `0002_clan_is_deleted`.

**`views/clan.py` split into `views/clan.py` + `views/clan_membership.py`.** File size management per code standards — would exceed 200 LOC if kept together. `clan.py` handles Clan CRUD; `clan_membership.py` handles member list/role/removal + invite create.

**Invite defaults NOT bounded in phase 2.** Spec listed phase 2 as implementation, but product decision to cap roles (`'editor'`/`'viewer'` only) and set 30-day default expiry came later during review-and-fix cycle. Phase 2 has unlimited `max_uses` and null `expires_at` (treated as never expires). Fixed post-review.

## Risk Assessment
- **Rò rỉ sự tồn tại của clan.** Trả 403 cho outsider là tiết lộ "clan này có thật". Bắt buộc 404.
- **Race condition ở `used_count`.** Không có `select_for_update`, một mã `max_uses=1` có thể bị dùng nhiều lần. MySQL InnoDB hỗ trợ, nhưng nhớ là code phải nằm trong `transaction.atomic`.
- **Rơi vào trạng thái không có owner** → clan bị khoá vĩnh viễn. Đã chặn ở bước 7.
