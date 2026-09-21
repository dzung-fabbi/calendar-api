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

# Hierarchy: owner (trưởng họ) > manager (Ban quản lý) > editor > viewer.
# Never compare role strings inline -- use the tuples in `giapha.permissions`
# (`EDITOR_ROLES`, `APPROVER_ROLES`) so adding a role is a one-file change.
CLAN_ROLE = (
    ('owner', 'Chủ sở hữu'),
    ('manager', 'Ban quản lý'),
    ('editor', 'Biên tập viên'),
    ('viewer', 'Người xem'),
)

# Role groups -- the ONLY place role strings are grouped. `permissions.py`
# re-exports them; selectors import them from here (no import cycle).
EDITOR_ROLES = ('owner', 'manager', 'editor')
# May approve invites (viewer role), verify bindings, review change requests.
APPROVER_ROLES = ('owner', 'manager')

# Roles an invite code may grant. Deliberately excludes 'owner' -- ownership
# transfer is a separate, explicit, owner-only action
# (`PATCH /clans/{id}/members/{user_id}`), never a side effect of redeeming a
# bearer code that could leak.
# Also excludes 'manager': Ban quản lý is only ever assigned by the owner.
INVITE_ROLE = (
    ('editor', 'Biên tập viên'),
    ('viewer', 'Người xem'),
)

# 'public' (bare) was never used anywhere but this tuple -- phase 9 replaces
# it with 'public_link', the actual state a clan is in once the owner mints
# a `Clan.public_slug`: a link exists, but there is no untargeted "public"
# mode where the clan is discoverable without one.
VISIBILITY = (
    ('private', 'Riêng tư'),
    ('public_link', 'Công khai qua link'),
)

# `pending_approval` invites have no code yet (NULL) -- the code is minted on
# approval, so a link never exists before an approver has seen the request.
INVITE_STATUS = (
    ('active', 'Đang hiệu lực'),
    ('pending_approval', 'Chờ duyệt'),
    ('rejected', 'Bị từ chối'),
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

# --- Gia phả cá nhân (`/v1/family`, spec docs/gia-pha-api-spec.md §3) ---
# English identifiers on purpose: the mobile app Person type uses these exact
# strings and the API echoes them verbatim -- no DB<->JSON mapping layer.
FAMILY_GENDER = (
    ('male', 'Nam'),
    ('female', 'Nữ'),
    ('unknown', 'Chưa rõ'),
)

FAMILY_PARENT_REL = (
    ('blood', 'Ruột'),
    ('adopted', 'Nuôi'),
)

FAMILY_SPOUSE_REL = (
    ('married', 'Đã kết hôn'),
    ('divorced', 'Ly hôn'),
)
