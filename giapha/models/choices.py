"""Choice tuples for the giapha models.

Values are unaccented Vietnamese so they stay stable ASCII identifiers in the
database; labels keep full diacritics for display in admin/API.
"""

GIOI_TINH = (
    ('nam', 'Nam'),
    ('nu', 'Nữ'),
    ('khac', 'Khác'),
)

PARENT_KIND = (
    ('ruot', 'Ruột'),
    ('nuoi', 'Nuôi'),
    ('ke', 'Kế'),
)

CLAN_ROLE = (
    ('owner', 'Chủ sở hữu'),
    ('editor', 'Biên tập viên'),
    ('viewer', 'Người xem'),
)

# Roles an invite code may grant. Deliberately excludes 'owner' -- ownership
# transfer is a separate, explicit, owner-only action
# (`PATCH /clans/{id}/members/{user_id}`), never a side effect of redeeming a
# bearer code that could leak.
INVITE_ROLE = (
    ('editor', 'Biên tập viên'),
    ('viewer', 'Người xem'),
)

VISIBILITY = (
    ('private', 'Riêng tư'),
    ('public', 'Công khai'),
)

MARRIAGE_STATUS = (
    ('dang_ket_hon', 'Đang kết hôn'),
    ('ly_hon', 'Ly hôn'),
    ('goa', 'Goá'),
)

REVISION_ACTION = (
    ('create', 'Tạo mới'),
    ('update', 'Cập nhật'),
    ('delete', 'Xoá'),
)
