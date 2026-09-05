"""View package. Re-exported flat so `giapha/urls.py` keeps its short imports."""

from giapha.views.clan import ClanDetailAPIView, ClanListCreateAPIView
from giapha.views.clan_membership import (
    ClanInviteDetailAPIView,
    ClanInviteListCreateAPIView,
    ClanMemberDetailAPIView,
    ClanMembersAPIView,
    JoinClanAPIView,
)
from giapha.views.device import DeviceTokenAPIView
from giapha.views.gio import ClanGioCalendarAPIView
from giapha.views.gio_follow import (
    ClanGioFollowDetailAPIView,
    ClanGioFollowListAPIView,
)
from giapha.views.marriage import MarriageDetailAPIView, MarriageListCreateAPIView
from giapha.views.member_binding import ClanMemberBindingAPIView
from giapha.views.person import PersonDetailAPIView
from giapha.views.person_list import PersonListCreateAPIView
from giapha.views.person_revision import PersonRestoreAPIView, PersonRevisionListAPIView
from giapha.views.tree import ClanTreeAPIView

__all__ = [
    'ClanDetailAPIView',
    'ClanGioCalendarAPIView',
    'ClanGioFollowDetailAPIView',
    'ClanGioFollowListAPIView',
    'ClanInviteDetailAPIView',
    'ClanInviteListCreateAPIView',
    'ClanListCreateAPIView',
    'ClanMemberBindingAPIView',
    'ClanMemberDetailAPIView',
    'ClanMembersAPIView',
    'ClanTreeAPIView',
    'DeviceTokenAPIView',
    'JoinClanAPIView',
    'MarriageDetailAPIView',
    'MarriageListCreateAPIView',
    'PersonDetailAPIView',
    'PersonListCreateAPIView',
    'PersonRestoreAPIView',
    'PersonRevisionListAPIView',
]
