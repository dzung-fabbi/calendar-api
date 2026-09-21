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
    INVITE_STATUS,
    MARRIAGE_STATUS,
    PARENT_KIND,
    REVISION_ACTION,
    VISIBILITY,
)
from giapha.models.change_request import CHANGE_REQUEST_ACTION, CHANGE_REQUEST_STATUS, ChangeRequest
from giapha.models.clan import Clan, ClanInvite, ClanMember
from giapha.models.device import DEVICE_PLATFORM, DeviceToken
from giapha.models.family import Family, FamilyPerson, FamilySpouse
from giapha.models.family_link import FamilyPersonLink
from giapha.models.gio_follow import GioFollow
from giapha.models.marriage import Marriage
from giapha.models.notification import GIO_NOTIFY_STATUS, GioNotificationLog
from giapha.models.person import Person
from giapha.models.revision import PersonRevision

__all__ = [
    'CHANGE_REQUEST_ACTION', 'CHANGE_REQUEST_STATUS', 'ChangeRequest',
    'CLAN_ROLE', 'DEVICE_PLATFORM', 'FAMILY_GENDER', 'FAMILY_PARENT_REL', 'FAMILY_SPOUSE_REL',
    'GIOI_TINH', 'GIO_NOTIFY_STATUS', 'INVITE_ROLE', 'INVITE_STATUS',
    'MARRIAGE_STATUS', 'PARENT_KIND', 'REVISION_ACTION', 'VISIBILITY',
    'Clan', 'ClanInvite', 'ClanMember', 'DeviceToken', 'Family', 'FamilyPerson', 'FamilyPersonLink', 'FamilySpouse',
    'GioFollow',
    'GioNotificationLog', 'Marriage', 'Person', 'PersonRevision',
]
