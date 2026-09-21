"""Admin for ChangeRequest (đề xuất thay đổi). Read-mostly: approving goes
through the API so the shared write path, revision and pushes all run.
"""

from django.contrib import admin

from giapha.models import ChangeRequest


@admin.register(ChangeRequest)
class ChangeRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'clan', 'action', 'status', 'proposer', 'reviewer', 'created_at')
    list_filter = ('status', 'action')
    raw_id_fields = ('clan', 'proposer', 'target_person', 'target_marriage', 'reviewer')
