"""Model package.

Re-exports every model so `from giapha.models import X` is the one import
path the rest of the app (and future migrations) rely on, mirroring
`apis/models/__init__.py`.
"""

from giapha.models.choices import (
    CLAN_ROLE,
    GIOI_TINH,
    INVITE_ROLE,
    MARRIAGE_STATUS,
    PARENT_KIND,
    REVISION_ACTION,
    VISIBILITY,
)
from giapha.models.clan import Clan, ClanInvite, ClanMember
from giapha.models.marriage import Marriage
from giapha.models.person import Person
from giapha.models.revision import PersonRevision

__all__ = [
    'CLAN_ROLE', 'GIOI_TINH', 'INVITE_ROLE', 'MARRIAGE_STATUS', 'PARENT_KIND',
    'REVISION_ACTION', 'VISIBILITY',
    'Clan', 'ClanInvite', 'ClanMember', 'Marriage', 'Person', 'PersonRevision',
]
