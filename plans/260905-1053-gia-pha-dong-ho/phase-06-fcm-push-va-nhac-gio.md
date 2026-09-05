---
phase: 6
title: "FCM push va nhac gio"
status: completed
priority: P1
effort: "3d"
dependencies: [5]
---

# Phase 6: FCM push + command nhắc giỗ

## Overview
Xây kênh gửi thông báo đẩy (chưa từng tồn tại trong codebase) và management command nhắc giỗ chạy hằng ngày, **gửi đúng người**: mặc định theo tổ tiên trực hệ, cho phép user tự thêm/bớt.

⚠️ **Một tiêu chí bị CHẶN:** "gửi push thật tới máy thử" cần Firebase service account JSON — chưa có. **Mọi tiêu chí còn lại phải đạt với FCM mock.** Xem [Trạng thái chặn](#trạng-thái-chặn).

✅ **ĐÃ SHIP (2026-09-05).** Code + review + fix + verify xong. **470 tests pass / 4 skipped**, `makemigrations giapha --check --dry-run` sạch, không đổi schema ngoài `0004`/`0005`. Review cuối: **8.5/10, shippable, 0 Critical/High mới**. Tiêu chí duy nhất còn treo: push thật tới máy thử (vẫn chờ Firebase JSON). Xem [Thực tế đã ship](#thực-tế-đã-ship-2026-09-05).

## Context Links
- [`plan.md`](./plan.md) → "Quyết định đã chốt (2026-09-05)" hàng #2
- [`phase-05-vn-lunar-va-lich-gio.md`](./phase-05-vn-lunar-va-lich-gio.md) — `services/gio.py` phase này tái sử dụng nguyên vẹn
- [`phase-04-tree-endpoint-va-generation.md`](./phase-04-tree-endpoint-va-generation.md) — `clan_edges` + pattern duyệt cây có safety counter
- `docs/code-standards.md` → Layering, Files, Queries

## Key Insights — đọc trước khi bắt đầu
- **Codebase hiện KHÔNG có kênh gửi thông báo nào.** `apis/management/commands/remind_appointment_date.py` chỉ ghi log; docstring của chính nó thừa nhận "has never delivered a reminder". `settings.py` không có SMTP, FCM, Firebase hay Celery.
- **FCM legacy server key đã bị Google tắt (6/2024).** Bắt buộc dùng **FCM HTTP v1** + service account JSON + OAuth2 token. Mọi hướng dẫn cũ nói về `Authorization: key=...` đều đã lỗi thời.
- Không có Celery → command chạy bằng **cron/scheduler ngoài** (host hoặc container). Đừng thêm Celery chỉ cho một job mỗi ngày (YAGNI).
- **[CRUX] User KHÔNG phải một node trong cây.** `ClanMember` (`giapha/models/clan.py:33`) chỉ nối `user` ↔ `clan` (`clan.py:35`, unique_together `('clan','user')` ở `clan.py:42`). `Person` (`giapha/models/person.py`) **không có** FK nào tới `auth.User` — đã grep toàn bộ `giapha/models/`: chỉ có `ClanMember.user`, `ClanInvite.created_by`, `PersonRevision.actor`. Không có đường nào đi từ một `User` ra "cụ tổ của chính người đó". **Không giải quyết được việc này thì không có "trực hệ".**

## Quyết định đã chốt — người nhận

| Hạng mục | Chốt |
|---|---|
| Ai nhận nhắc giỗ | **Tổ tiên trực hệ của chính người nhận: mặc định BẬT** |
| Tuỳ biến | User **tự thêm** người ngoài trực hệ, **tự bớt** người trong trực hệ |
| Lưu ở đâu | Bảng `GioFollow(person, user, enabled)` — **chỉ lưu phần khác mặc định** |
| Không còn đúng | ~~Gửi cho mọi `ClanMember` của clan~~ — đã bỏ, đó là nguồn spam |

## Architecture

### A. Ràng buộc user ↔ Person — `ClanMember.person`

**Chốt: thêm `ClanMember.person` (OneToOne, nullable). KHÔNG thêm `Person.user`.**

```python
# giapha/models/clan.py  -- sửa ClanMember
person = models.OneToOneField(
    'giapha.Person', on_delete=models.SET_NULL, null=True, blank=True,
    related_name='member_link', verbose_name='Là ai trong cây',
)
```

| Vì sao `ClanMember.person` chứ không `Person.user` | |
|---|---|
| Tính duy nhất cho không | "một user ↔ một Person mỗi clan" đã có sẵn từ `unique_together ('clan','user')` (`clan.py:42`). `Person.user` phải thêm một `unique_together ('clan','user')` mới trên `Person` mới đạt cùng điều đó. |
| Rời họ thì đứt liên kết | Xoá `ClanMember` → binding biến mất, node `Person` (dữ liệu tổ tiên) ở lại. Với `Person.user`, người đã rời họ vẫn còn con trỏ → **vẫn nhận push của một clan mình không còn quyền đọc**. Đây là lỗi rò rỉ thật, không phải khẩu vị. |
| Đúng ngữ nghĩa | "Trong họ này, tôi là người này" là thuộc tính của **tư cách thành viên**, không phải của con người. Một user ở 3 họ có 3 binding khác nhau. |

- `OneToOneField` ⇒ một node `Person` chỉ được **một** user nhận. MySQL cho phép nhiều `NULL` trong unique index, nên "chưa nhận" không đụng nhau. Đây là lý do chọn OneToOne thay vì `FK + unique=True` thủ công — cùng DDL, ít chữ hơn.
- `on_delete=SET_NULL` (**không** CASCADE): hard-delete một `Person` qua Django admin mà kéo theo cả `ClanMember` là **đá user ra khỏi họ và xoá luôn vai trò `owner`** của họ. Không bao giờ.
- **DB không ép được `person.clan_id == member.clan_id`** (MySQL không có composite FK tới `(clan_id, id)`). Ép ở tầng app: serializer của endpoint binding lọc `Person` theo `clan_id` lấy từ URL, cộng `ClanMember.clean()` cho đường admin. Ghi rõ giới hạn này trong docstring model.

**Migration:** `0004_clanmember_person_binding.py` — **thuần additive, cột nullable, KHÔNG backfill**. Không có dữ liệu nào để đoán ai là ai; mọi hàng hiện có bắt đầu ở `NULL`. Reversible sạch (`RemoveField`). Deploy không downtime (ADD COLUMN + ADD INDEX trên bảng vài nghìn hàng).

**Hệ quả bắt buộc phải xử lý:** member **chưa binding ⇒ KHÔNG có trực hệ ⇒ không nhận nhắc mặc định** (chỉ nhận những gì tự thêm). Đây là hành vi trung thực duy nhất — đoán bừa còn tệ hơn im lặng. `GET .../toi-la` trả `null` để client hiện lời mời "chọn bạn là ai trong cây".

### B. `GioFollow` — bảng **override**, không phải bảng danh sách

```python
# giapha/models/gio_follow.py
class GioFollow(models.Model):
    person     FK(Person, on_delete=CASCADE, related_name='gio_follows')
    user       FK(auth.User, on_delete=CASCADE, related_name='gio_follows')
    enabled    BooleanField()          # KHÔNG có default -- luôn phải nói rõ ý
    created_at, updated_at
    class Meta: unique_together = ('person', 'user')
```

**Ba trạng thái, chỉ hai được lưu:**

| Trạng thái | Biểu diễn | Ý nghĩa |
|---|---|---|
| Mặc định | **không có hàng nào** | trực hệ → theo dõi; ngoài trực hệ → không |
| Bật thủ công | hàng `enabled=True` | theo dõi người ngoài trực hệ (cha nuôi, thầy, bên ngoại xa) |
| Tắt thủ công | hàng `enabled=False` | bỏ một cụ trong trực hệ |

**Vì sao mặc định là *ngầm*, phân giải lúc gửi — không materialize sẵn hàng:**
- Materialize buộc phải **đồng bộ lại mỗi khi cây đổi**: sửa `father`/`mother`, tạo person, xoá mềm, member join, binding đổi. Đó là bài toán invalidate fan-out cho một job **chạy một lần mỗi ngày**. Phase 4 đã có một race trên field denormalise (`generation`, M6 — deferred); thêm cấu trúc denormalise thứ hai là nhân đôi đúng lớp bug đó.
- Hàng materialize **hỏng trong im lặng**: user thêm cụ tổ mới tìm được vào cây, không có push, không có lỗi, không ai biết. Phân giải ngầm tự lành.
- Chi phí phân giải gần bằng 0: `clan_edges(clan_id)` (`giapha/selectors/person.py:14`) là **1 query**, chặn ở 5.000 người; duyệt tổ tiên là vi giây.
- Không cần migration backfill, không cần command `resync_gio_follows`.

**Index:** không thêm gì. `unique_together ('person','user')` cho index dẫn đầu bởi `person`; hai FK tự có `db_index` của Django ⇒ truy vấn theo `user` cũng có index. Câu lệnh của command lọc `person__clan_id=<clan>` — đi qua FK index của `Person.clan`. Thêm index nữa ở quy mô này là đoán mò (YAGNI).

**Cascade:** `person` CASCADE (theo dõi một người đã bị hard-delete là vô nghĩa), `user` CASCADE (xoá tài khoản là xoá sạch). Soft-delete `Person` **không** đụng `GioFollow` — command đã lọc `is_deleted=False` ở `deceased_with_lunar_death` (`giapha/selectors/gio.py:28`), hàng override nằm im vô hại và sống lại đúng nếu person được khôi phục.

### C. Phân giải "trực hệ" — thuần, test bằng `SimpleTestCase`

`giapha/services/gio_follow.py` (thuần, **không ORM** — đúng luật Layering của `docs/code-standards.md`):

```
ancestors(edges, person_id) -> set[int]
    # duyệt ngược father/mother từ person_id, KHÔNG gồm chính person_id
    # edges là [(id, father_id, mother_id), ...] -- đúng shape clan_edges trả về
    # safety counter 2*len(edges)+10, y hệt services/person_rules.descendants
    #   (person_rules.py:34) và services/tree.subtree_ids: dữ liệu vào bằng
    #   Django admin có thể đã chứa chu trình.
    # KHÁC person_rules.descendants ở một điểm: hàm này fail OPEN (trả tập đã
    #   duyệt được) chứ không raise. Đây là job nền, không phải cổng ghi --
    #   thiếu vài người nhận còn hơn cả lượt nhắc giỗ chết vì một hàng hỏng.

followers_by_person(edges, bindings, overrides, person_ids) -> {person_id: set[user_id]}
    # bindings : {user_id: self_person_id}   (chỉ member đã binding)
    # overrides: {(user_id, person_id): enabled}
    # với mỗi user: base = ancestors(edges, self_person_id) ∩ person_ids
    #               followed = (base - {p | override False}) | {p | override True}
    # override BẬT vẫn phải nằm trong person_ids (người có giỗ đến hạn của clan này)
```

**"Trực hệ" = tổ tiên đi lên (cha/mẹ truy hồi), KHÔNG gồm con cháu, KHÔNG gồm bàng hệ** (anh em, chú bác, anh em họ). Khớp đúng chữ "duyệt tổ tiên trực hệ khi gửi" ở `plan.md`. Giỗ của một người con đã mất là chuyện thật nhưng hiếm — user **tự thêm** bằng override `enabled=True`. Đó chính là lý do có nửa "thêm" của quyết định; đừng nhét thêm một quy tắc mặc định thứ hai (YAGNI).

Cả cha lẫn mẹ đều được truy hồi ⇒ trực hệ gồm cả bên nội và bên ngoại **có mặt trong cây**. Không lọc theo giới tính, không lọc theo `branch`.

### D. Model gửi/log — giữ nguyên phase gốc

```python
# giapha/models/device.py
class DeviceToken(models.Model):
    user        FK(auth.User, related_name='device_tokens')
    token       CharField(255, unique, db_index)
    platform    CharField(choices=['ios','android','web'])
    is_active   BooleanField(default=True)
    last_seen   DateTimeField(auto_now)
    created_at

# giapha/models/notification.py
class GioNotificationLog(models.Model):
    person      FK(Person)
    user        FK(auth.User)
    solar_date  DateField(db_index)     # ngày giỗ được nhắc
    sent_at     DateTimeField(auto_now_add)
    status      CharField(choices=['sent','failed'])
    error       CharField(255, blank)
    class Meta: unique_together = ('person', 'user', 'solar_date')
```
`unique_together` trên log là **cơ chế chống gửi trùng**: chạy lại command trong cùng ngày sẽ vướng constraint và bỏ qua. Đơn giản hơn nhiều so với lưu trạng thái riêng.

### Cấu hình nhắc
Thêm vào `Clan`: `gio_remind_before_days IntegerField(default=3)` — cả họ dùng chung một thiết lập. Cho phép mỗi user tự chỉnh số ngày là YAGNI ở MVP (quyết định #2 chỉ chốt *ai nhận*, không chốt *nhắc trước mấy ngày*).

### Luồng command `remind_death_anniversary`
```
today = today_vn()                       # services/gio.py:47 -- KHÔNG dùng localdate()
for clan in Clan (is_deleted=False):
    target = today + clan.gio_remind_before_days
    rows,_ = deceased_with_lunar_death(clan.id, MAX_CLAN_PERSONS)   # Q1
    due = [r for r in rows if có occurrence == target]              # services/gio.py, thuần
    if not due: continue          # <-- thoát TRƯỚC 4 query dưới; ngày thường mọi clan đều rơi vào đây
    edges     = clan_edges(clan.id)                                 # Q2
    bindings  = binding_map(clan.id)         # ClanMember có person != NULL   Q3
    overrides = overrides_for_clan(clan.id)  # GioFollow của clan này          Q4
    followers = followers_by_person(edges, bindings, overrides, {r.id for r in due})
    tokens    = active_tokens_for(user_ids)                          # Q5
    for (person, user) in cặp có token: gửi push, ghi GioNotificationLog
```
- Tính giỗ bằng `services/gio.py` của phase 5 (`gio_occurrence`, `gio.py:52`) — **không** đọc `AppointmentDate`, **không** materialize sẵn hàng nghìn dòng.
- **Chi phí query: 1/clan ở ngày không có giỗ, 5/clan ở ngày có giỗ.** Với 1.000 clan, một ngày bình thường là ~1.000 query cho job nền — chấp nhận được, không phải request người dùng. Việc `continue` sớm là điều làm cho con số này ổn; đừng đảo thứ tự.
- Người nhận **đến từ `GioFollow` resolution**, không còn là "mọi `ClanMember` của clan".

### Gửi FCM
`giapha/services/fcm.py`:
- Gọi thẳng **HTTP v1** bằng `google-auth` + `requests` (`requests` đã có trong requirements). **Không** dùng `firebase-admin`: nó kéo theo nhiều dependency trong khi ta chỉ cần một endpoint gửi.
- Token trả lỗi `UNREGISTERED` hoặc `INVALID_ARGUMENT` → set `is_active=False`.
- Credential đọc từ `FIREBASE_CREDENTIALS_JSON` (nội dung JSON) hoặc `FIREBASE_CREDENTIALS_PATH`. **Không commit file service account.**
- Khi thiếu credential: command log cảnh báo và thoát sạch (exit 0), **không** raise — cron sẽ ồn vô ích.
- Lưu ý layering: `services/fcm.py` gọi mạng nhưng **không đụng ORM** → vẫn hợp luật. Việc đánh dấu `is_active=False` nằm ở command/selector, không nằm trong `fcm.py`.

### Nội dung thông báo
```
Tiêu đề: "Sắp đến ngày giỗ"
Nội dung: "Còn 3 ngày nữa là giỗ {ho_ten} (đời {generation}) — {ngày} tháng {tháng} âm lịch, nhằm {dd/mm/yyyy}."
data: {"type": "gio", "clan_id": ..., "person_id": ...}
```

## Related Code Files

**Create**
- `giapha/models/gio_follow.py`, `giapha/models/device.py`, `giapha/models/notification.py`
- `giapha/migrations/0004_clanmember_person_binding.py`
- `giapha/migrations/0005_giofollow_devicetoken_notificationlog_remindbefore.py`
- `giapha/services/gio_follow.py` — `ancestors`, `followers_by_person` (thuần)
- `giapha/services/fcm.py`
- `giapha/selectors/gio_follow.py` — `binding_map`, `overrides_for_clan`, `active_tokens_for`, `follow_rows_for_user`
- `giapha/serializers/gio_follow.py`, `giapha/serializers/device.py`
- `giapha/views/gio_follow.py`, `giapha/views/device.py`
- `giapha/management/commands/remind_death_anniversary.py`
- `giapha/tests/test_gio_follow_service.py` (SimpleTestCase), `giapha/tests/test_gio_follow_api.py`, `giapha/tests/test_remind_command.py`

**Modify**
- `giapha/models/clan.py` — `ClanMember.person` + `Clan.gio_remind_before_days`
- `giapha/models/__init__.py`, `giapha/views/__init__.py`, `giapha/serializers/__init__.py`, `giapha/urls.py` — re-export phẳng theo đúng nếp hiện có
- `giapha/admin/clan.py` — cho `person` vào `ClanMemberInline`
- `giapha/tests/factories.py` — helper binding user ↔ person cho fixture
- `.env.example` — `FIREBASE_CREDENTIALS_PATH`
- `requirements.txt` — `google-auth`
- `docs/deployment-guide.md` — cách đặt cron
- `docker-compose.yml` / `scripts/` — ghi chú chạy cron hằng ngày

Tên module: **`snake_case`**, không kebab-case — `docs/code-standards.md` → Files nói rõ Python không import được `kebab-case`. Mọi file dưới 200 dòng.

## Endpoints

Tiền tố như hiện tại: `/api/gia-pha/`. Mọi endpoint clan-scoped dùng `IsAuthenticated + IsClanMember` — khớp `ClanGioCalendarAPIView` và đường `clans/<int:clan_id>/lich-gio` (`giapha/urls.py:38`).

```
GET    /clans/{clan_id}/toi-la                     IsClanMember   -> {person_id, ho_ten} hoặc null
PUT    /clans/{clan_id}/toi-la                     IsClanMember   body {person_id}  -> đặt binding
DELETE /clans/{clan_id}/toi-la                     IsClanMember   -> gỡ binding (person=NULL)

GET    /clans/{clan_id}/gio-follows                IsClanMember   -> danh sách ĐÃ PHÂN GIẢI
PUT    /clans/{clan_id}/gio-follows/{person_id}    IsClanMember   body {enabled: bool} -> upsert override
DELETE /clans/{clan_id}/gio-follows/{person_id}    IsClanMember   -> xoá override, VỀ MẶC ĐỊNH

POST   /devices                                    IsAuthenticated  body {token, platform}  (upsert theo token)
DELETE /devices                                    IsAuthenticated  body {token}            (logout)
```

- **`PUT` + `DELETE` chứ không phải `POST /follow` + `DELETE /follow`.** Đây là ba trạng thái, không phải hai: `PUT {enabled:false}` = "bỏ cụ này", `DELETE` = "trả về mặc định". Thiếu `DELETE` thì user tắt nhầm một cụ rồi **không bao giờ quay lại trạng thái mặc định** được nữa.
- `GET /gio-follows` trả danh sách **đã phân giải**, mỗi hàng có `source: 'truc-he' | 'thu-cong' | 'da-bo'` để client giải thích được vì sao một người có/không có mặt. Chỉ liệt kê người **đã mất có đủ ngày+tháng âm** — người sống không có giỗ để theo.
- **`/devices` KHÔNG được dùng `IsClanMember`**: `permissions._role_for` đọc `view.kwargs['clan_id']` (`giapha/permissions.py:29`), route này không có `clan_id` ⇒ resolve `None` và ném 404. `IsAuthenticated` là đúng và đủ — device token thuộc về user, không thuộc về clan.
- `POST /devices` với token đã tồn tại của user khác → chuyển sở hữu token sang user mới (máy dùng chung / đăng nhập lại).

## Implementation Steps

1. **Binding trước tiên.** `ClanMember.person` + migration `0004`. Cột nullable, không backfill. Cập nhật `admin/clan.py` và `tests/factories.py`. Chạy `makemigrations giapha --check --dry-run` để chắc không sinh migration lạc.
2. Endpoint `toi-la` (3 method). Validate: `person` phải thuộc `clan_id` của URL, `is_deleted=False`, **chưa bị member khác nhận** (đụng OneToOne → 400 "Người này đã được thành viên khác nhận", không để `IntegrityError` thành 500), và **không phải người đã mất**. Không cho owner binding hộ người khác — self-service, lọc theo `request.user` (theo `docs/code-standards.md` → Serializers).
3. `services/gio_follow.py`: `ancestors` + `followers_by_person`. **Viết test `SimpleTestCase` trước khi viết bất cứ thứ gì chạm DB** — đây là phần dễ sai nhất và rẻ nhất để test. Ca bắt buộc: không cha mẹ; chỉ có mẹ; cả hai bên nội ngoại; cây sâu 10 đời; chu trình do admin nhập (phải dừng, không hang); user chưa binding; override bật cho người bàng hệ; override tắt cho cụ tổ.
4. `models/gio_follow.py`, `models/device.py`, `models/notification.py`, `Clan.gio_remind_before_days` + migration `0005`. `DeviceToken.token` unique để `POST` là upsert thật.
5. `selectors/gio_follow.py` + endpoint `gio-follows` (3 method). Ràng buộc query: `GET` phải là **số query cố định**, không phụ thuộc số người theo dõi.
6. `services/fcm.py` với **một** hàm public `send_multicast(tokens, title, body, data) -> {token: ok|error}`. Tách riêng lớp lấy OAuth token (cache theo TTL, không xin token mới mỗi lần gửi).
7. Endpoint `/devices` (POST/DELETE), `IsAuthenticated`.
8. Command. Cấu trúc **hai nửa**: `collect_due(today)` (làm query + gọi hàm thuần, trả list việc cần gửi **kèm người nhận đã phân giải**) tách khỏi `dispatch(jobs)` (gửi thật) → test được toàn bộ phần tính toán mà không đụng mạng.
9. Test command: **mock hoàn toàn lớp FCM**, không gọi mạng trong test. Phủ: đúng ngày mới gửi; chạy hai lần không gửi trùng; thiếu credential thì thoát sạch; một token lỗi không chặn token còn lại; **member chưa binding không nhận gì**; **chỉ trực hệ nhận, người trong họ nhưng bàng hệ KHÔNG nhận**; override bật/tắt được tôn trọng; clan không có giỗ đến hạn chỉ tốn 1 query.
10. Ghi cron vào `docs/deployment-guide.md` (ví dụ `0 7 * * * python manage.py remind_death_anniversary`).
11. **Cân nhắc (không bắt buộc):** nối `apis/management/commands/remind_appointment_date.py` vào cùng `services/fcm.py`. Món quà DRY rõ ràng — nhưng nó **sửa `apis/`**, nên chỉ làm khi phase 10 đã xanh, và làm thành commit riêng.

## Todo List

- [x] `ClanMember.person` + migration `0004` + admin + factories
- [x] Endpoint `toi-la` (GET/PUT/DELETE) + validation cross-clan / đã bị nhận / người đã mất — tách ra `views/member_binding.py`
- [x] `services/gio_follow.py` thuần + `test_gio_follow_service.py` (SimpleTestCase, 21 test)
- [x] Models `GioFollow` / `DeviceToken` / `GioNotificationLog` / `Clan.gio_remind_before_days` + migration `0005`
- [x] `selectors/gio_follow.py` + endpoint `gio-follows` (GET/PUT/DELETE) + `assertNumQueries(5)` cố định
- [x] `services/fcm.py` (HTTP v1, OAuth cache TTL) — tách `services/fcm_auth.py` khi vượt 200 dòng
- [x] Endpoint `/devices` (POST/DELETE), `IsAuthenticated`
- [x] Command `remind_death_anniversary` (`collect_due` / `dispatch`) + `services/gio_remind.py` + `_gio_reminder_log.py`
- [x] `test_remind_command.py` — FCM mock hoàn toàn (17 test)
- [x] Cron + `.env.example` + `requirements.txt` (`google-auth==2.29.0`) + `.gitignore` + `docs/deployment-guide.md` (file mới)

## Success Criteria

**Đạt được với FCM mock (bắt buộc, không có ngoại lệ):**
- [x] Binding: `PUT /clans/{id}/toi-la` gắn được user vào một Person; person của clan khác → 400; person đã bị member khác nhận → 400 (không phải 500) — có thêm test race thật, `transaction.atomic()` chống `TransactionManagementError`
- [x] Rời họ (xoá `ClanMember`) → binding biến mất, node `Person` còn nguyên
- [x] Command chỉ gửi cho **tổ tiên trực hệ** của người nhận: member bàng hệ trong cùng clan **không** nhận
- [x] Member **chưa binding** không nhận nhắc mặc định nào
- [x] `PUT gio-follows/{pid} {enabled:false}` trên một cụ tổ → lượt chạy sau không gửi cụ đó
- [x] `PUT gio-follows/{pid} {enabled:true}` trên người ngoài trực hệ → lượt chạy sau có gửi
- [x] `DELETE gio-follows/{pid}` → quay lại đúng trạng thái mặc định (bật nếu trực hệ, tắt nếu không)
- [x] `ancestors` dừng gọn trên cây có chu trình do admin nhập: không hang, không raise (fail OPEN)
- [x] Command chạy 2 lần trong ngày chỉ gửi 1 lần — **cơ chế đã đổi**: dedupe đọc `notified_pairs` lọc `status='sent'` + `log_attempt` `update_or_create`, chứ không dựa vào `IntegrityError` của `unique_together` nữa. Đổi để lần chạy sau **retry được** hàng `failed` (H1). Hệ quả: xem NEW-1 ở `plan.md`.
- [x] Token chết bị đánh dấu `is_active=False` sau lần gửi lỗi (`ERROR_NETWORK` **không** bị tắt)
- [x] Thiếu credential → command thoát code 0 kèm cảnh báo, không stacktrace
- [x] Một token lỗi không làm dừng lượt gửi (thêm: một lỗi ghi log cũng không, `try/except` mỗi recipient)
- [x] **Không test nào gọi mạng thật** — `requests.post` + `_mint_token` patch ở mọi chỗ
- [x] `assertNumQueries`: `GET gio-follows` **5 query cố định** (pin 2 lần: fixture 4 người và chuỗi 30 đời + 20 override); command **1 query/clan** khi clan không có giỗ đến hạn
- [x] Command với 100 clan chạy < 30s — đo **0.12s**. Test đo giờ đã xoá, **không commit** (timing assert flaky trong CI) ⇒ không có regression guard.
- [x] `makemigrations giapha --check --dry-run` sạch sau khi xong

**Bị chặn (chỉ nghiệm thu khi có Firebase JSON):**
- [ ] 🔒 Gửi được push **thật** tới một máy thử — **VẪN CHƯA ĐẠT.** Chưa có ai chạy với Firebase project thật. Toàn bộ đường FCM mới chỉ được nghiệm thu qua mock + một smoke test google-auth với private key cố tình hỏng.

## Thực tế đã ship (2026-09-05)

Báo cáo nguồn (đừng suy lại từ source):
[models+api](../reports/fullstack-260905-1739-phase-06-models-api.md) ·
[services+fcm](../reports/fullstack-260905-1739-phase-06-services-fcm.md) ·
[command](../reports/fullstack-260905-1749-phase-06-remind-command.md) ·
[review](../reports/code-reviewer-260905-1806-phase-06-fcm-gio-follow.md) ·
[fix](../reports/fullstack-260905-1817-phase-06-review-fixes.md) ·
[verify](../reports/code-reviewer-260905-1837-phase-06-fix-verification.md)

**Số liệu:** 357 → **470 pass / 4 skip**. Migration check sạch. Không đổi schema ngoài `0004`/`0005`. Mọi file production < 200 dòng. Review vòng 1: 1 Critical, 3 High, 5 Medium, 6 Low — **đã fix hết**; verify vòng 2: 0 Critical/High mới, **8.5/10**.

### Khác kế hoạch (file sinh thêm, đều do luật 200 dòng hoặc luật Layering)

| File | Vì sao |
|---|---|
| `giapha/views/member_binding.py` | `views/gio_follow.py` chạm 239 dòng → tách `toi-la` khỏi phần phân giải follow. Tiền lệ `views/person.py` / `views/person_list.py`. |
| `giapha/services/fcm_auth.py` | `fcm.py` chạm 269 dòng sau fix H2 → tách nửa OAuth. Còn 149/151. Import là DAG, không vòng. |
| `giapha/management/commands/_gio_reminder_log.py` | Command chạm 224 dòng → hai hàm ghi ORM (`deactivate_dead`, `log_attempt`) chuyển ra. Tiền tố `_` để Django `find_commands` bỏ qua. **Không** để trong `services/` vì nó ghi ORM. |
| `giapha/services/gio_remind.py` | Nửa thuần của command (`GioJob`, `message_body`, `due_rows`) — kế hoạch không nêu tên file này. |
| `selectors/person.clan_edges_all` | Xem M1 bên dưới. |

Selector sinh thêm (Layering cấm ORM inline trong view): `member_binding`, `person_claimed_by_other`, `notified_pairs`, `overrides_for_clan`.

### Quyết định của chủ dự án đã chốt trong session này

1. **C1 (Critical, rò rỉ push cho người đã rời họ) — fix bằng JOIN membership, KHÔNG xoá dữ liệu.** `overrides_for_clan` lọc thêm `user__clanmember__clan_id=clan_id`. Chọn phương án **không phá huỷ**: hàng `GioFollow` sống sót khi member bị gỡ ⇒ **vào lại họ thì khôi phục nguyên tuỳ chọn cũ**. `unique_together ('clan','user')` giữ join 1:1 nên không cần `distinct()`, số query không đổi.
2. **M1 (tổ tiên bị xoá mềm làm đứt dòng trực hệ) — fix CHỈ trong phạm vi phase 6.** Thêm `clan_edges_all` (gồm cả hàng `is_deleted=True`); **`clan_edges` giữ nguyên byte-for-byte** để không đụng hợp đồng phase 4 và phần xưng hô của phase 7. Hai selector đều có ghi chú "DO NOT UNIFY". Dùng ở command **và** `GET /gio-follows` — nếu để hai bên phân giải khác nhau thì màn hình nói user theo dõi một người mà push không bao giờ gửi. Không người xoá mềm nào lọt ra response (candidate vẫn lấy từ `deceased_with_lunar_death`).
3. **Chiếm quyền device token (L5) — GIỮ NGUYÊN, là rủi ro đã chấp nhận và có spec.** `POST /devices` với token của user khác vẫn chuyển sở hữu (máy dùng chung / đăng nhập lại). Nay ghi thành *quyết định* trong docstring `views/device.py`, không còn là tai nạn.

## Trạng thái chặn

**BLOCKED — cần Firebase project + service account JSON.** Vẫn chưa có (2026-09-05, sau khi phase đã ship).

Điều này **không** chặn việc bắt đầu phase. Toàn bộ mục A–C (binding, `GioFollow`, phân giải trực hệ, các endpoint) và cả command với `services/fcm.py` mock **làm và nghiệm thu được ngay**. Chỉ đúng một tiêu chí — push tới máy thật — phải chờ. Làm theo thứ tự Implementation Steps ở trên thì phần bị chặn nằm gọn ở cuối; đừng để nó chặn 90% còn lại.

**Kết quả:** đã đúng như dự đoán — 16/17 tiêu chí đạt với mock, chỉ tiêu chí push thật còn treo. Khi có JSON: chỉ cần đặt `FIREBASE_CREDENTIALS_PATH`/`_JSON` (đã khai trong `settings.py`, `.env.example`, và `docker-compose.yml` đã forward vào container từ session này) rồi chạy command — không cần sửa code.

## Risk Assessment

| Rủi ro | Khả năng × Ảnh hưởng | Giảm thiểu |
|---|---|---|
| **Không ai binding ⇒ không ai nhận gì.** Tính năng im lặng, trông như hỏng. | Cao × Cao | `GET /toi-la` trả `null` tường minh; ghi vào docs API rằng client **phải** hỏi "bạn là ai trong cây" sau khi join họ. Cân nhắc trả thêm cờ `binding_required` trong `GET /clans/{id}` ở phase 9/10. |
| **Cây thưa ⇒ trực hệ rỗng.** User binding vào một node chưa khai cha mẹ → 0 tổ tiên → 0 nhắc. | Cao × Trung bình | Đúng theo thiết kế, không phải bug. `GET /gio-follows` trả rỗng + client gợi ý bổ sung cha/mẹ. Không được "chữa" bằng cách rơi về gửi cả họ — đó chính là thứ quyết định #2 loại bỏ. |
| Chu trình cha-con làm `ancestors` hang | Thấp × Cao | Safety counter `2*len(edges)+10`, y hệt `person_rules.descendants` (`person_rules.py:34`). Fail **open** (trả tập một phần) vì đây là job nền, không phải cổng ghi. Có test ép chạm cap. |
| `person.clan_id != member.clan_id` lọt qua Django admin | Trung bình × Trung bình | DB không ép được (không có composite FK). `ClanMember.clean()` + validate ở serializer. Ghi giới hạn vào docstring model. |
| ~~Spam cả họ 200 người~~ | **ĐÃ GỠ** | Quyết định #2: trực hệ + override. Người nhận trung bình giảm từ O(số member) xuống O(số hậu duệ trực hệ). |
| **Đây là hạ tầng mới hoàn toàn** (FCM), không có tiền lệ trong repo | Trung bình × Trung bình | Ước lượng 3d có thể trượt nếu khâu Firebase credential vướng thủ tục. Xem Trạng thái chặn. |
| Rò rỉ credential | Thấp × Cao | Service account JSON không bao giờ vào git. Thêm `.gitignore` ngay bước đầu của phần FCM. |
| **Timezone — đã xác nhận là vấn đề thật.** `djangopj/settings.py:137` đặt `TIME_ZONE = 'UTC'` (với `USE_TZ = True` ở `:143`). `timezone.localdate()` trả **ngày UTC**: cron chạy trước 07:00 giờ VN tính nhầm sang ngày hôm trước → nhắc giỗ lệch một ngày. | Cao × Cao | Dùng `services.gio.today_vn()` (`gio.py:47`, đã có từ phase 5) — **không** `timezone.localdate()`, **không** tự viết lại `VN_TZ`. **Không** đổi `TIME_ZONE` toàn cục: `apis/` và các golden snapshot đang dựa trên hành vi hiện tại. Ghi chú: `apis/.../remind_appointment_date.py` cũng dính đúng lỗi này — ngoài phạm vi, nhưng nên báo lại chủ dự án. |
| Migration `0004`/`0005` xung đột với phase 8/9 chạy song song | Thấp × Thấp | Phase 6 giữ số `0004`–`0005`; phase 8/9 lấy số sau. Không phase nào khác sửa `ClanMember`. |

**Rollback:** `0005` gỡ độc lập (xoá 3 bảng + 1 cột `Clan`, không có dữ liệu ngoài nào phụ thuộc). `0004` gỡ sau, làm mất binding user↔person đã nhập — chấp nhận được vì user khai lại được, nhưng **nếu đã lên production và có người dùng thật thì dump cột `clanmember.person_id` trước khi revert**.

## Security Considerations
- Mọi endpoint clan-scoped đứng sau `IsAuthenticated + IsClanMember`; người ngoài nhận **404** chứ không 403 (nếp của `giapha/permissions.py`, để không xác nhận clan có tồn tại).
- `GET /gio-follows` chỉ trả **người đã mất** của clan mà caller đã là thành viên — không mở thêm bề mặt dữ liệu nào so với `GET /tree` và `GET /lich-gio` mà caller vốn đã gọi được. Không có PII người sống.
- Override + binding luôn lọc theo `request.user`, **không bao giờ** theo `user_id` do client gửi.
- Device token là dữ liệu nhạy cảm: không log toàn bộ token, không đưa vào response của endpoint nào khác.
- Nội dung push chứa tên người đã mất → chấp nhận được (đó là mục đích), nhưng **không** đưa thông tin người sống vào payload.

## Next Steps
- **Phụ thuộc vào:** phase 5 (`services/gio.py`) ✅ xong; phase 3/4 (`Person`, `clan_edges`) ✅ xong.
- **Chặn ngoài codebase:** Firebase service account JSON.
- **Kéo theo:** phase 10 cập nhật `docs/system-architecture.md` (kênh push mới, bảng binding) và `docs/codebase-summary.md`.
- **Mở đường cho:** `ClanMember.person` là thứ phase 7 (máy tính xưng hô) cũng cần — "tôi gọi người này là gì" chỉ có nghĩa khi biết "tôi" là node nào. Làm ở phase 6 là làm sớm một dependency của phase 7, không phải làm thừa.

## Câu hỏi mở

1. **Owner binding hộ member khác?** MVP: không, self-service. Nhưng cụ ông 80 tuổi không tự thao tác được — có cần `PUT /clans/{id}/members/{user_id}/toi-la` cho owner không?
2. **Nhắc trước mấy ngày là cấu hình cấp clan** (`gio_remind_before_days`). Có ai sẽ đòi cấu hình theo user, hoặc nhiều mốc (7 ngày *và* 1 ngày)? Hiện tại một mốc, một clan.
3. **Giỗ của con cháu đã mất** hiện phải tự thêm bằng override. Nếu thực tế đa số user đều thêm, mặc định nên là "trực hệ hai chiều" (tổ tiên ∪ hậu duệ) — đo bằng tỉ lệ override `enabled=True` sau khi ship.
4. **User ở nhiều clan cùng lúc** nhận push từ tất cả. Có cần tắt nhắc theo từng clan (`ClanMember.gio_muted`) không? Chưa thấy nhu cầu, chưa làm.
5. **Người đã mất mà cũng từng là một `User`** (tài khoản của người vừa qua đời): binding vẫn còn, DeviceToken vẫn còn. Không xử lý ở MVP; đáng ghi vào câu hỏi lưu trữ dữ liệu #4 của `plan.md`.
6. **Đổi cha/mẹ trong cây làm đổi tập trực hệ ngay lập tức** — không có thông báo cho user rằng danh sách theo dõi của họ vừa thay đổi. Đúng theo thiết kế phân giải ngầm, nhưng có thể gây bất ngờ.
7. **`ancestors` fail open vs `descendants` fail closed** là mâu thuẫn có chủ đích giữa hai module cùng hình dạng. Đã ghi lý do trong docstring — review lại ở phase 10 xem có nên thống nhất không.
