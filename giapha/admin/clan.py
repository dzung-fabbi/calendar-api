"""Admin for Clan and its member roster."""

from django.contrib import admin

from giapha.models import Clan, ClanInvite, ClanMember


class ClanMemberInline(admin.TabularInline):
    """`person` is a `raw_id_field`, not a dropdown: the widget would
    otherwise render every Person in the database, and a 5.000-person clan
    makes the Clan admin page unusable.

    The clan-mismatch check that `ModelForm` validation runs here comes from
    `ClanMember.clean()` -- the admin is exactly the path the database cannot
    guard (no composite FK in MySQL).
    """

    model = ClanMember
    extra = 0
    raw_id_fields = ('user', 'person')


@admin.register(Clan)
class ClanAdmin(admin.ModelAdmin):
    list_display = ('id', 'ten_ho', 'visibility', 'hide_living_details', 'gio_remind_before_days', 'created_at')
    list_filter = ('visibility', 'hide_living_details')
    search_fields = ('ten_ho', 'thuy_to')
    inlines = [ClanMemberInline]


@admin.register(ClanInvite)
class ClanInviteAdmin(admin.ModelAdmin):
    list_display = ('id', 'clan', 'code', 'role', 'expires_at', 'used_count', 'max_uses')
    list_filter = ('role',)
    search_fields = ('code',)
    raw_id_fields = ('clan', 'created_by')
