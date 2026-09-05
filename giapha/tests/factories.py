"""Fixture builders for the giapha test-suite.

`build_clan_fixture()` wires up one clan with a user in each role plus an
outsider unrelated to it -- phases 3+ reuse this heavily to set up
permission-scoped tests without repeating the wiring in every module.
"""

from django.contrib.auth.models import User

from giapha.models import Clan, ClanMember, Person


def build_clan_fixture(ten_ho='Nguyễn tộc', suffix=''):
    """Returns a dict: `clan`, `owner`, `editor`, `viewer`, `outsider`.

    `owner`/`editor`/`viewer` are already `ClanMember`s of `clan` with the
    matching role; `outsider` has no relation to it at all. Pass a distinct
    `suffix` if a single test needs more than one fixture (usernames must be
    unique).
    """
    clan = Clan.objects.create(ten_ho=ten_ho)

    owner = User.objects.create_user(username='clan_owner' + suffix, password='pw')
    editor = User.objects.create_user(username='clan_editor' + suffix, password='pw')
    viewer = User.objects.create_user(username='clan_viewer' + suffix, password='pw')
    outsider = User.objects.create_user(username='clan_outsider' + suffix, password='pw')

    ClanMember.objects.create(clan=clan, user=owner, role='owner')
    ClanMember.objects.create(clan=clan, user=editor, role='editor')
    ClanMember.objects.create(clan=clan, user=viewer, role='viewer')

    return {
        'clan': clan,
        'owner': owner,
        'editor': editor,
        'viewer': viewer,
        'outsider': outsider,
    }


def build_person(clan, ho_ten='Người thử nghiệm', gioi_tinh='nam', **overrides):
    """A minimal valid Person in `clan`. Pass `father=`/`mother=` (Person
    instances) or any other model field as an override.
    """
    return Person.objects.create(clan=clan, ho_ten=ho_ten, gioi_tinh=gioi_tinh, **overrides)
