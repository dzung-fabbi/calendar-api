from django.urls import path

from giapha.views import (
    ClanDetailAPIView,
    ClanGioCalendarAPIView,
    ClanGioFollowDetailAPIView,
    ClanGioFollowListAPIView,
    ClanInviteDetailAPIView,
    ClanInviteListCreateAPIView,
    ClanKinshipAPIView,
    ClanListCreateAPIView,
    ClanMemberBindingAPIView,
    ClanMemberDetailAPIView,
    ClanMembersAPIView,
    ClanPhotoUrlsAPIView,
    ClanPublicLinkAPIView,
    ClanPublicPersonDetailAPIView,
    ClanPublicTreeAPIView,
    ClanTreeAPIView,
    DeviceTokenAPIView,
    JoinClanAPIView,
    MarriageDetailAPIView,
    MarriageListCreateAPIView,
    PersonDetailAPIView,
    PersonListCreateAPIView,
    PersonPhotoAPIView,
    PersonPhotoUploadUrlAPIView,
    PersonRestoreAPIView,
    PersonRevisionListAPIView,
)

urlpatterns = [
    path('clans', ClanListCreateAPIView.as_view(), name='clan-list-create'),
    path('clans/<int:clan_id>', ClanDetailAPIView.as_view(), name='clan-detail'),
    path('clans/<int:clan_id>/members', ClanMembersAPIView.as_view(), name='clan-members'),
    path(
        'clans/<int:clan_id>/members/<int:user_id>',
        ClanMemberDetailAPIView.as_view(),
        name='clan-member-detail',
    ),
    path('clans/<int:clan_id>/invites', ClanInviteListCreateAPIView.as_view(), name='clan-invite-create'),
    path(
        'clans/<int:clan_id>/invites/<int:invite_id>',
        ClanInviteDetailAPIView.as_view(),
        name='clan-invite-detail',
    ),
    path('join', JoinClanAPIView.as_view(), name='clan-join'),

    path('clans/<int:clan_id>/lich-gio', ClanGioCalendarAPIView.as_view(), name='clan-lich-gio'),

    # "Tôi là ai trong cây" -- the binding every default reminder depends on.
    path('clans/<int:clan_id>/toi-la', ClanMemberBindingAPIView.as_view(), name='clan-toi-la'),
    path(
        'clans/<int:clan_id>/gio-follows',
        ClanGioFollowListAPIView.as_view(),
        name='clan-gio-follows',
    ),
    path(
        'clans/<int:clan_id>/gio-follows/<int:person_id>',
        ClanGioFollowDetailAPIView.as_view(),
        name='clan-gio-follow-detail',
    ),

    # Not clan-scoped on purpose -- a device token belongs to the user.
    path('devices', DeviceTokenAPIView.as_view(), name='device-token'),

    # Máy tính xưng hô. `a` mặc định là chính người gọi (ClanMember.person).
    path('clans/<int:clan_id>/xung-ho', ClanKinshipAPIView.as_view(), name='clan-xung-ho'),

    path('clans/<int:clan_id>/tree', ClanTreeAPIView.as_view(), name='clan-tree'),

    path('clans/<int:clan_id>/persons', PersonListCreateAPIView.as_view(), name='person-list-create'),
    path(
        'clans/<int:clan_id>/persons/<int:person_id>',
        PersonDetailAPIView.as_view(),
        name='person-detail',
    ),
    path(
        'clans/<int:clan_id>/persons/<int:person_id>/revisions',
        PersonRevisionListAPIView.as_view(),
        name='person-revisions',
    ),
    path(
        'clans/<int:clan_id>/persons/<int:person_id>/restore/<int:revision_id>',
        PersonRestoreAPIView.as_view(),
        name='person-restore',
    ),

    # Presigned S3/R2 photo upload (phase 8). No bytes ever cross Django --
    # see `giapha/services/storage.py` / `giapha/views/photo.py`.
    path(
        'clans/<int:clan_id>/persons/<int:person_id>/photo-upload-url',
        PersonPhotoUploadUrlAPIView.as_view(),
        name='person-photo-upload-url',
    ),
    path(
        'clans/<int:clan_id>/persons/<int:person_id>/photo',
        PersonPhotoAPIView.as_view(),
        name='person-photo',
    ),
    path('clans/<int:clan_id>/photo-urls', ClanPhotoUrlsAPIView.as_view(), name='clan-photo-urls'),

    path('clans/<int:clan_id>/marriages', MarriageListCreateAPIView.as_view(), name='marriage-list-create'),
    path(
        'clans/<int:clan_id>/marriages/<int:marriage_id>',
        MarriageDetailAPIView.as_view(),
        name='marriage-detail',
    ),

    # Phase 9 -- chia sẻ công khai. Owner-only toggle lives under
    # `clans/{clan_id}/...` (auth); the two `public/{slug}/...` routes below
    # are the no-auth surface a slug actually resolves to.
    path('clans/<int:clan_id>/public-link', ClanPublicLinkAPIView.as_view(), name='clan-public-link'),
    path('public/<str:slug>/tree', ClanPublicTreeAPIView.as_view(), name='public-clan-tree'),
    path(
        'public/<str:slug>/persons/<int:person_id>',
        ClanPublicPersonDetailAPIView.as_view(),
        name='public-person-detail',
    ),
]
