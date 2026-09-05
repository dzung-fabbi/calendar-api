"""View package. Re-exported flat so `giapha/urls.py` keeps its short imports."""

from giapha.views.clan import ClanDetailAPIView, ClanListCreateAPIView
from giapha.views.clan_membership import (
    ClanInviteDetailAPIView,
    ClanInviteListCreateAPIView,
    ClanMemberDetailAPIView,
    ClanMembersAPIView,
    JoinClanAPIView,
)
from giapha.views.gio import ClanGioCalendarAPIView
from giapha.views.marriage import MarriageDetailAPIView, MarriageListCreateAPIView
from giapha.views.person import PersonDetailAPIView
from giapha.views.person_list import PersonListCreateAPIView
from giapha.views.person_revision import PersonRestoreAPIView, PersonRevisionListAPIView
from giapha.views.tree import ClanTreeAPIView

__all__ = [
    'ClanDetailAPIView',
    'ClanGioCalendarAPIView',
    'ClanInviteDetailAPIView',
    'ClanInviteListCreateAPIView',
    'ClanListCreateAPIView',
    'ClanMemberDetailAPIView',
    'ClanMembersAPIView',
    'ClanTreeAPIView',
    'JoinClanAPIView',
    'MarriageDetailAPIView',
    'MarriageListCreateAPIView',
    'PersonDetailAPIView',
    'PersonListCreateAPIView',
    'PersonRestoreAPIView',
    'PersonRevisionListAPIView',
]
