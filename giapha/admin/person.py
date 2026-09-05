"""Admin for Person and Marriage.

`raw_id_fields` on father/mother is mandatory: a plain dropdown over every
Person row across every clan would hang the admin page once data grows.
"""

from django.contrib import admin

from giapha.models import Marriage, Person


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ('id', 'ho_ten', 'clan', 'gioi_tinh', 'generation', 'branch', 'is_deleted')
    list_filter = ('clan', 'generation', 'gioi_tinh', 'is_deleted')
    search_fields = ('ho_ten', 'ten_huy')
    raw_id_fields = ('father', 'mother', 'clan')


@admin.register(Marriage)
class MarriageAdmin(admin.ModelAdmin):
    list_display = ('id', 'husband', 'wife', 'order', 'status')
    list_filter = ('status',)
    raw_id_fields = ('husband', 'wife')
