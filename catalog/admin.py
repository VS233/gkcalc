from django.contrib import admin
from .models import Stat, Item, ItemStat, ItemSet, SetBonus, Effect


class ItemStatInline(admin.TabularInline):
    model = ItemStat
    extra = 3
    fields = ['stat', 'base_value']


class SetBonusInline(admin.TabularInline):
    model = SetBonus
    extra = 2
    fields = ['pieces_required', 'stat', 'value', 'effect']


@admin.register(Effect)
class EffectAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']


@admin.register(ItemSet)
class ItemSetAdmin(admin.ModelAdmin):
    list_display = ['name', 'rarity', 'item_count']
    list_filter = ['rarity']
    search_fields = ['name']
    inlines = [SetBonusInline]

    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = 'Предметов'


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'slot_type', 'rarity', 'item_set', 'is_active']
    list_filter = ['slot_type', 'rarity', 'item_set', 'is_active']
    search_fields = ['name']
    inlines = [ItemStatInline]


@admin.register(Stat)
class StatAdmin(admin.ModelAdmin):
    list_display = ['name_ru', 'slug', 'category', 'order', 'is_percent']
    list_editable = ['order']
    ordering = ['order']


@admin.register(ItemStat)
class ItemStatAdmin(admin.ModelAdmin):
    list_display = ['item', 'stat', 'base_value']
    list_filter = ['stat']


@admin.register(SetBonus)
class SetBonusAdmin(admin.ModelAdmin):
    list_display = ['item_set', 'pieces_required', 'stat', 'value', 'effect']
    list_filter = ['item_set']