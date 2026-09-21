"""View package. Re-exported flat so `giapha/urls.py` keeps its short imports."""

from giapha.views.change_request import ChangeRequestDetailAPIView, ChangeRequestListCreateAPIView
from giapha.views.change_request_review import ChangeRequestApproveAPIView, ChangeRequestRejectAPIView
from giapha.views.clan import ClanDetailAPIView, ClanListCreateAPIView, ClanPublicLinkAPIView
from giapha.views.clan_invite import ClanInviteDetailAPIView, ClanInviteListCreateAPIView
from giapha.views.clan_join import JoinClanAPIView
from giapha.views.clan_membership import ClanMemberDetailAPIView, ClanMembersAPIView
from giapha.views.invite_review import ClanInviteApproveAPIView, ClanInviteRejectAPIView
from giapha.views.device import DeviceTokenAPIView
from giapha.views.family import (
    FamilyGioEventAPIView,
    FamilyPersonCreateAPIView,
    FamilyPersonDetailAPIView,
    FamilyRootAPIView,
    FamilySelfAPIView,
)
from giapha.views.family_import import FamilyImportAPIView
from giapha.views.family_link import (
    FamilyLinkDetailAPIView,
    FamilyLinkDiffAPIView,
    FamilyLinkListCreateAPIView,
    FamilyLinkSuggestionsAPIView,
)
from giapha.views.family_link_contribute import FamilyLinkContributeAPIView
from giapha.views.family_link_flow_clan import FamilyClanBootstrapAPIView
from giapha.views.family_link_import import FamilyLinkImportAPIView
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
from giapha.views.member_verify import ClanMemberVerifyAPIView
from giapha.views.person import PersonDetailAPIView
from giapha.views.person_list import PersonListCreateAPIView
from giapha.views.person_revision import PersonRestoreAPIView, PersonRevisionListAPIView
from giapha.views.photo import PersonPhotoAPIView, PersonPhotoUploadUrlAPIView
from giapha.views.photo_urls import ClanPhotoUrlsAPIView
from giapha.views.public import ClanPublicPersonDetailAPIView, ClanPublicTreeAPIView
from giapha.views.tree import ClanTreeAPIView

__all__ = [
    'ChangeRequestApproveAPIView',
    'ChangeRequestDetailAPIView',
    'ChangeRequestListCreateAPIView',
    'ChangeRequestRejectAPIView',
    'ClanDetailAPIView',
    'ClanGioCalendarAPIView',
    'ClanGioFollowDetailAPIView',
    'ClanGioFollowListAPIView',
    'ClanInviteApproveAPIView',
    'ClanInviteDetailAPIView',
    'ClanInviteListCreateAPIView',
    'ClanInviteRejectAPIView',
    'ClanKinshipAPIView',
    'ClanListCreateAPIView',
    'ClanMemberBindingAPIView',
    'ClanMemberDetailAPIView',
    'ClanMemberVerifyAPIView',
    'ClanMembersAPIView',
    'ClanPhotoUrlsAPIView',
    'ClanPublicLinkAPIView',
    'ClanPublicPersonDetailAPIView',
    'ClanPublicTreeAPIView',
    'ClanTreeAPIView',
    'DeviceTokenAPIView',
    'FamilyAddRelativeAPIView',
    'FamilyClanBootstrapAPIView',
    'FamilyGioEventAPIView',
    'FamilyImportAPIView',
    'FamilyLinkContributeAPIView',
    'FamilyLinkDetailAPIView',
    'FamilyLinkDiffAPIView',
    'FamilyLinkImportAPIView',
    'FamilyLinkListCreateAPIView',
    'FamilyLinkSuggestionsAPIView',
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
