"""Admin for Clan and its member roster."""

from django.contrib import admin

from giapha.models import Clan, ClanInvite, ClanMember


class ClanMemberInline(admin.TabularInline):
    model = ClanMember
    extra = 0
    raw_id_fields = ('user',)


@admin.register(Clan)
class ClanAdmin(admin.ModelAdmin):
    list_display = ('id', 'ten_ho', 'visibility', 'hide_living_details', 'created_at')
    list_filter = ('visibility', 'hide_living_details')
    search_fields = ('ten_ho', 'thuy_to')
    inlines = [ClanMemberInline]


@admin.register(ClanInvite)
class ClanInviteAdmin(admin.ModelAdmin):
    list_display = ('id', 'clan', 'code', 'role', 'expires_at', 'used_count', 'max_uses')
    list_filter = ('role',)
    search_fields = ('code',)
    raw_id_fields = ('clan', 'created_by')
