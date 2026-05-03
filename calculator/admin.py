from django.contrib import admin
from .models import Doll, DollSlot, DollSkill


class DollSlotInline(admin.TabularInline):
    model = DollSlot
    extra = 0
    fields = ['slot_type', 'item', 'grade', 'quality']


@admin.register(Doll)
class DollAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'character_level', 'is_public', 'updated_at']
    list_filter = ['is_public']
    readonly_fields = ['uuid']
    inlines = [DollSlotInline]
