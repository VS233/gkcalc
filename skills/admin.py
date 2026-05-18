from django.contrib import admin
from .models import SkillNode, SkillEdge, SkillBonus


class SkillBonusInline(admin.TabularInline):
    model  = SkillBonus
    extra  = 2
    fields = ['stat', 'value_level_1', 'value_level_2', 'value_level_3']


@admin.register(SkillNode)
class SkillNodeAdmin(admin.ModelAdmin):
    list_display  = ['name', 'section', 'branch', 'order', 'max_points']
    list_filter   = ['section', 'branch']
    ordering      = ['section', 'branch', 'order']
    list_editable = ['order', 'max_points']
    search_fields = ['name']
    inlines       = [SkillBonusInline]


@admin.register(SkillEdge)
class SkillEdgeAdmin(admin.ModelAdmin):
    list_display = ['from_node', 'to_node', 'edge_type']
    list_filter  = ['from_node__section', 'edge_type']


@admin.register(SkillBonus)
class SkillBonusAdmin(admin.ModelAdmin):
    list_display  = ['node', 'stat', 'value_level_1', 'value_level_2', 'value_level_3']
    list_filter   = ['node__section', 'node__branch']
    list_editable = ['value_level_1', 'value_level_2', 'value_level_3']