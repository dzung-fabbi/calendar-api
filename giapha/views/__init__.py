"""View package. Re-exported flat so `giapha/urls.py` keeps its short imports."""

from giapha.views.clan import ClanDetailAPIView, ClanListCreateAPIView, ClanPublicLinkAPIView
from giapha.views.clan_membership import (
    ClanInviteDetailAPIView,
    ClanInviteListCreateAPIView,
    ClanMemberDetailAPIView,
    ClanMembersAPIView,
    JoinClanAPIView,
)
from giapha.views.device import DeviceTokenAPIView
from giapha.views.family import (
    FamilyGioEventAPIView,
    FamilyPersonCreateAPIView,
    FamilyPersonDetailAPIView,
    FamilyRootAPIView,
    FamilySelfAPIView,
)
from giapha.views.family_relations import (
    FamilyAddRelativeAPIView,
    FamilyLinkChildAPIView,
    FamilyLinkSpouseAPIView,
    FamilySetParentAPIView,
    FamilyUnlinkSpouseAPIView,
)
from giapha.views.gio import ClanGioCalendarAPIView
from giapha.views.gio_follow import (
    ClanGioFollowDetailAPIView,
    ClanGioFollowListAPIView,
)
from giapha.views.kinship import ClanKinshipAPIView
from giapha.views.marriage import MarriageDetailAPIView, MarriageListCreateAPIView
from giapha.views.member_binding import ClanMemberBindingAPIView
from giapha.views.person import PersonDetailAPIView
from giapha.views.person_list import PersonListCreateAPIView
from giapha.views.person_revision import PersonRestoreAPIView, PersonRevisionListAPIView
from giapha.views.photo import PersonPhotoAPIView, PersonPhotoUploadUrlAPIView
from giapha.views.photo_urls import ClanPhotoUrlsAPIView
from giapha.views.public import ClanPublicPersonDetailAPIView, ClanPublicTreeAPIView
from giapha.views.tree import ClanTreeAPIView

__all__ = [
    'ClanDetailAPIView',
    'ClanGioCalendarAPIView',
    'ClanGioFollowDetailAPIView',
    'ClanGioFollowListAPIView',
    'ClanInviteDetailAPIView',
    'ClanInviteListCreateAPIView',
    'ClanKinshipAPIView',
    'ClanListCreateAPIView',
    'ClanMemberBindingAPIView',
    'ClanMemberDetailAPIView',
    'ClanMembersAPIView',
    'ClanPhotoUrlsAPIView',
    'ClanPublicLinkAPIView',
    'ClanPublicPersonDetailAPIView',
    'ClanPublicTreeAPIView',
    'ClanTreeAPIView',
    'DeviceTokenAPIView',
    'FamilyAddRelativeAPIView',
    'FamilyGioEventAPIView',
    'FamilyLinkChildAPIView',
    'FamilyLinkSpouseAPIView',
    'FamilyPersonCreateAPIView',
    'FamilyPersonDetailAPIView',
    'FamilyRootAPIView',
    'FamilySelfAPIView',
    'FamilySetParentAPIView',
    'FamilyUnlinkSpouseAPIView',
    'JoinClanAPIView',
    'MarriageDetailAPIView',
    'MarriageListCreateAPIView',
    'PersonDetailAPIView',
    'PersonListCreateAPIView',
    'PersonPhotoAPIView',
    'PersonPhotoUploadUrlAPIView',
    'PersonRestoreAPIView',
    'PersonRevisionListAPIView',
]
