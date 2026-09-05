---
phase: 1
title: "Scaffold app va models"
status: completed
priority: P1
effort: "1d"
dependencies: []
---

# Phase 1: Scaffold app `giapha/` + models + migrations + admin

## Overview
Dựng Django app mới `giapha/` với đầy đủ phân lớp theo chuẩn repo, khai báo toàn bộ model của module, sinh migration đầu tiên, và đăng ký admin.

## Requirements
- Functional: app `giapha` cài được, `manage.py migrate` chạy sạch, admin hiển thị và sửa được Clan/Person/Marriage.
- Non-functional: mỗi file model < 200 dòng; `models/` chỉ chứa định nghĩa trường, **không có behaviour**; không import gì từ `apis/`.

## Architecture

Sao chép đúng phân lớp của `apis/` (xem `docs/system-architecture.md`):

```
giapha/
├── __init__.py
├── apps.py                 GiaPhaConfig(name='giapha')
├── urls.py
├── models/
│   ├── __init__.py         re-export phẳng, giống apis/models/__init__.py
│   ├── choices.py          GIOI_TINH, PARENT_KIND, CLAN_ROLE, VISIBILITY, MARRIAGE_STATUS
│   ├── clan.py             Clan, ClanMember, ClanInvite
│   ├── person.py           Person
│   ├── marriage.py         Marriage
│   └── revision.py         PersonRevision
├── selectors/__init__.py
├── services/__init__.py
├── serializers/__init__.py
├── views/__init__.py
├── admin/
│   ├── __init__.py
│   ├── clan.py
│   └── person.py
├── management/commands/    (rỗng ở phase này)
└── tests/__init__.py
```

Phụ thuộc một chiều: `views -> serializers/selectors/services -> models`. `services/` **không** import ORM (để test bằng `SimpleTestCase`).

## Related Code Files

**Create**
- `giapha/` toàn bộ cây thư mục trên
- `giapha/migrations/0001_initial.py` (sinh bằng `makemigrations`)

**Modify**
- `djangopj/settings.py` — thêm `'giapha.apps.GiaPhaConfig'` vào `INSTALLED_APPS`, thêm hằng `MAX_CLAN_PERSONS = 5000`
- `djangopj/urls.py` — thêm `path('api/gia-pha/', include('giapha.urls'))`

**Không đụng vào** `apis/` ở phase này.

## Schema chi tiết

### `models/clan.py`
```python
class Clan(models.Model):
    ten_ho          CharField(255)                  # "Họ Nguyễn Đình"
    thuy_to         CharField(255, blank)           # tên thuỷ tổ
    mo_ta           TextField(blank)
    visibility      CharField(choices=VISIBILITY, default='private')
    public_slug     CharField(32, unique, null)     # sinh ở phase 9
    hide_living_details BooleanField(default=True)
    created_at / updated_at

class ClanMember(models.Model):
    clan  FK(Clan, related_name='members')
    user  FK(auth.User)
    role  CharField(choices=CLAN_ROLE)              # owner | editor | viewer
    joined_at
    class Meta: unique_together = ('clan', 'user')

class ClanInvite(models.Model):
    clan       FK(Clan, related_name='invites')
    code       CharField(12, unique, db_index)
    role       CharField(choices=CLAN_ROLE, default='viewer')
    expires_at DateTimeField(null)
    max_uses   IntegerField(default=0)              # 0 = không giới hạn
    used_count IntegerField(default=0)
    created_by FK(auth.User, null)
```

### `models/person.py`
```python
class Person(models.Model):
    clan        FK(Clan, related_name='persons', db_index)

    # Danh xưng — gia phả VN cần đủ bộ, không cắt bớt
    ho_ten      CharField(255, db_index)
    ten_huy     CharField(255, blank)   # tên huý (kiêng gọi sau khi mất)
    ten_tu      CharField(255, blank)
    ten_hieu    CharField(255, blank)
    thuy_hieu   CharField(255, blank)   # dùng trong văn khấn

    gioi_tinh   CharField(choices=GIOI_TINH)        # nam | nu | khac

    # Quan hệ dọc
    father      FK('self', null, related_name='children_as_father')
    mother      FK('self', null, related_name='children_as_mother')
    parent_kind CharField(choices=PARENT_KIND, default='ruot')  # ruot|nuoi|ke

    # Vị trí trong họ
    generation  IntegerField(null, db_index)   # đời thứ mấy, tính ở phase 4
    branch      CharField(255, blank, db_index)  # chi/nhánh
    birth_order IntegerField(null)             # con thứ mấy
    is_truong   BooleanField(default=False)    # con trưởng

    # Sinh
    birth_solar DateField(null)
    birth_lunar_day / birth_lunar_month IntegerField(null)
    birth_lunar_leap BooleanField(default=False)

    # Mất — GIỖ TÍNH THEO ÂM LỊCH, ngày dương chỉ là tham chiếu
    death_solar DateField(null)
    death_lunar_day   IntegerField(null)   # 1..30
    death_lunar_month IntegerField(null)   # 1..12
    death_lunar_leap  BooleanField(default=False)

    # Hồ sơ
    que_quan     CharField(255, blank)
    nghe_nghiep  CharField(255, blank)
    tieu_su      TextField(blank)
    photo_key    CharField(255, blank)     # key S3/R2, phase 8

    # Mộ phần
    mo_phan_lat  DecimalField(9,6, null)
    mo_phan_lng  DecimalField(9,6, null)
    mo_phan_note CharField(255, blank)

    is_deleted   BooleanField(default=False)   # soft delete
    created_at / updated_at

    class Meta:
        indexes = [(clan, generation), (clan, branch), (clan, death_lunar_month, death_lunar_day)]
```

Index cuối là index phục vụ truy vấn lịch giỗ ở phase 5 — thêm ngay từ đầu.

`is_living` **không** là cột: suy ra bằng `death_solar is None and death_lunar_day is None`. Đặt thành `@property` trên model? **Không** — `models/` không chứa behaviour; đặt hàm `is_living(person)` trong `services/`.

### `models/marriage.py`
```python
class Marriage(models.Model):
    husband FK(Person, related_name='marriages_as_husband')
    wife    FK(Person, related_name='marriages_as_wife')
    order   IntegerField(default=1)    # 1 = vợ cả, 2+ = vợ lẽ / tái hôn
    status  CharField(choices=MARRIAGE_STATUS)  # dang_ket_hon | ly_hon | goa
    note    CharField(255, blank)
    class Meta: unique_together = ('husband', 'wife')
```

### `models/revision.py`
```python
class PersonRevision(models.Model):
    person       FK(Person, related_name='revisions')
    actor        FK(auth.User, null)
    action       CharField(choices=['create','update','delete'])
    payload_json TextField()      # snapshot trước khi đổi, JSON
    created_at   DateTimeField(auto_now_add, db_index)
```

Dùng `TextField` chứa JSON, **không** `JSONField` — MySQL 5.7 + Django 3.1 hỗ trợ kém.

## Implementation Steps
1. `python manage.py startapp giapha`, rồi tái cấu trúc thành các package theo cây trên (xoá `models.py`, `views.py`, `admin.py`, `tests.py` mặc định).
2. Viết `giapha/models/choices.py` — mọi tuple choices, đặt tên tiếng Việt không dấu cho value, label có dấu.
3. Viết 4 file model theo schema trên. Chỉ định nghĩa trường + `Meta` + `__str__`.
4. `giapha/models/__init__.py` re-export phẳng toàn bộ model và choices (migration sẽ tham chiếu).
5. Thêm `verbose_name` / `verbose_name_plural` tiếng Việt cho mọi model (nhất quán với `apis/models/booking.py`).
6. Đăng ký app trong `INSTALLED_APPS`, thêm `MAX_CLAN_PERSONS = 5000` vào settings.
7. Tạo `giapha/urls.py` với `urlpatterns = []` và nối vào `djangopj/urls.py`.
8. `python manage.py makemigrations giapha` → review `0001_initial.py` bằng mắt (kiểm tra index và FK `to_field`).
9. Viết `giapha/admin/` — `ClanAdmin` (inline `ClanMember`), `PersonAdmin` (`list_filter` theo clan/generation, `search_fields` ho_ten/ten_huy, `raw_id_fields` cho father/mother để tránh dropdown khổng lồ).
10. Chạy `./scripts/run-tests.sh` để chắc chắn migration mới không phá suite hiện có.

## Success Criteria
- [x] `python manage.py migrate` chạy sạch trên MySQL 5.7
- [x] `python manage.py check` không cảnh báo
- [x] Admin tạo/sửa được Clan, Person (chọn cha/mẹ qua raw_id), Marriage
- [x] Không file model nào vượt 200 dòng
- [x] `grep -r "from apis" giapha/` không có kết quả
- [x] Bộ test hiện có của `apis/` vẫn xanh

## Deviations from spec

**None.** Phase 1 spec was followed exactly. `Clan.is_deleted` was NOT added here — it was introduced in phase 2 per the discovery during implementation that phase 2 required soft-delete semantics for clan membership API.

## Risk Assessment
- **`raw_id_fields` bắt buộc cho father/mother.** Không có nó, admin render dropdown chứa toàn bộ Person của mọi clan → treo trang khi dữ liệu lớn.
- **Đặt index lịch giỗ muộn sẽ tốn một migration nữa.** Thêm ngay ở `0001_initial`.
- **`JSONField` không dùng được** trên Django 3.1 + MySQL 5.7 một cách tin cậy → đã chọn `TextField`.
- Django 3.1 dùng `AppConfig` kiểu cũ (không auto-discover) → phải khai báo `'giapha.apps.GiaPhaConfig'` đầy đủ, không viết tắt `'giapha'`.
