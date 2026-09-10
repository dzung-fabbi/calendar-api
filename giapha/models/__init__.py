"""Model package.

Re-exports every model so `from giapha.models import X` is the one import
path the rest of the app (and future migrations) rely on, mirroring
`apis/models/__init__.py`.
"""

from giapha.models.choices import (
    CLAN_ROLE,
    FAMILY_GENDER,
    FAMILY_PARENT_REL,
    FAMILY_SPOUSE_REL,
    GIOI_TINH,
    INVITE_ROLE,
    MARRIAGE_STATUS,
    PARENT_KIND,
    REVISION_ACTION,
    VISIBILITY,
)
from giapha.models.clan import Clan, ClanInvite, ClanMember
from giapha.models.device import DEVICE_PLATFORM, DeviceToken
from giapha.models.family import Family, FamilyPerson, FamilySpouse
from giapha.models.gio_follow import GioFollow
from giapha.models.marriage import Marriage
from giapha.models.notification import GIO_NOTIFY_STATUS, GioNotificationLog
from giapha.models.person import Person
from giapha.models.revision import PersonRevision

__all__ = [
    'CLAN_ROLE', 'DEVICE_PLATFORM', 'FAMILY_GENDER', 'FAMILY_PARENT_REL', 'FAMILY_SPOUSE_REL',
    'GIOI_TINH', 'GIO_NOTIFY_STATUS', 'INVITE_ROLE',
    'MARRIAGE_STATUS', 'PARENT_KIND', 'REVISION_ACTION', 'VISIBILITY',
    'Clan', 'ClanInvite', 'ClanMember', 'DeviceToken', 'Family', 'FamilyPerson', 'FamilySpouse',
    'GioFollow',
    'GioNotificationLog', 'Marriage', 'Person', 'PersonRevision',
]
