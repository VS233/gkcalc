"""
Сервисный слой — вся логика расчёта статов здесь.
Views только вызывают эти функции — бизнес-логика не смешивается с HTTP.
"""
from collections import defaultdict
from catalog.models import Stat, SlotType


def calculate_doll_stats(doll):
    """
    Считает итоговые статы куклы:
      базовые статы персонажа
      + статы от предметов
      + бонусы от сетов
      + бонусы от навыков
    """
    from django.conf import settings as django_settings
    from catalog.models import SetBonus
    totals = defaultdict(float)

    # 0. Базовые статы персонажа
    for slug, value in django_settings.BASE_CHARACTER_STATS.items():
        totals[slug] += value

    # 1. Статы от предметов + считаем сколько предметов из каждого сета
    set_counts = defaultdict(int)
    for doll_slot in doll.slots.select_related('item__item_set').prefetch_related(
        'item__stats__stat', 'custom_stats__stat'
    ):
        if not doll_slot.item:
            continue
        for slug, value in doll_slot.get_effective_stats().items():
            totals[slug] += value
        if doll_slot.item.item_set_id:
            set_counts[doll_slot.item.item_set_id] += 1

    # 2. Бонусы от сетов
    for set_id, count in set_counts.items():
        bonuses = SetBonus.objects.filter(
            item_set_id=set_id,
            pieces_required__lte=count,
            stat__isnull=False,
        ).select_related('stat')
        for bonus in bonuses:
            totals[bonus.stat.slug] += bonus.value

    # 3. Бонусы от навыков
    for doll_skill in doll.skill_points.select_related('node').prefetch_related('node__bonuses__stat'):
        if doll_skill.points_invested > 0:
            for bonus in doll_skill.node.bonuses.all():
                totals[bonus.stat.slug] += bonus.get_value_for_points(doll_skill.points_invested)

    return dict(totals)


def get_stats_grouped(doll):
    """
    Возвращает статы куклы, сгруппированные по категории (мощь / сопротивление),
    с названиями из справочника Stat.
    """
    raw = calculate_doll_stats(doll)
    stats_qs = Stat.objects.all().order_by('order')

    power = []
    resistance = []
    for stat in stats_qs:
        entry = {
            'slug': stat.slug,
            'name': stat.name_ru,
            'value': raw.get(stat.slug, 0),
            'is_percent': stat.is_percent,
        }
        if stat.category == Stat.CATEGORY_POWER:
            power.append(entry)
        else:
            resistance.append(entry)

    return {'power': power, 'resistance': resistance}


def get_available_points(doll):
    """Сколько очков навыков доступно. Уровень 1 = 0 очков, уровень 2 = 1 очко и т.д."""
    spent = sum(
        ds.points_invested for ds in doll.skill_points.all()
    )
    total = max(0, doll.character_level - 1)
    return max(0, total - spent)


def get_total_points(doll):
    """Всего очков по уровню."""
    return max(0, doll.character_level - 1)


def get_spent_points(doll):
    """Потрачено очков."""
    return sum(ds.points_invested for ds in doll.skill_points.all())


def is_over_budget(doll):
    """Потрачено больше очков чем доступно по уровню."""
    return get_spent_points(doll) > get_total_points(doll)


def can_unlock_node(doll, node):
    """
    Проверяет, доступен ли узел для прокачки.
    Правило: хотя бы ОДИН родительский узел должен быть полностью заполнен.
    Если входящих рёбер нет — узел первого ряда, всегда доступен.
    """
    edges = list(node.edges_to.select_related('from_node').all())
    if not edges:
        return True

    for edge in edges:
        parent = edge.from_node
        invested = doll.skill_points.filter(node=parent).values_list(
            'points_invested', flat=True
        ).first() or 0
        if invested >= parent.max_points:
            return True  # нашли хотя бы одного заполненного родителя

    return False


def can_remove_point(doll, node):
    """
    Проверяет, можно ли убрать очко из узла.
    Нельзя откатить узел если от него зависит уже прокачанный дочерний узел.
    """
    from skills.models import SkillEdge

    def is_invested(child):
        invested = doll.skill_points.filter(node=child).values_list(
            'points_invested', flat=True
        ).first() or 0
        return invested > 0

    def node_is_full(n):
        invested = doll.skill_points.filter(node=n).values_list(
            'points_invested', flat=True
        ).first() or 0
        return invested >= n.max_points

    # Смотрим все рёбра ОТ этого узла (дочерние)
    for edge in node.edges_from.select_related('to_node').all():
        child = edge.to_node
        if not is_invested(child):
            continue  # дочерний не прокачан — ок

        # Дочерний прокачан — проверяем есть ли у него другой заполненный родитель
        # (альтернативный путь через диагональ)
        child_edges = list(child.edges_to.select_related('from_node').all())
        other_parents_ok = any(
            e.from_node.pk != node.pk and node_is_full(e.from_node)
            for e in child_edges
        )
        if not other_parents_ok:
            return False  # дочерний зависит только от нас — откат запрещён

    return True


def save_stats_snapshot(doll):
    """Сохраняет снапшот статов в doll.stats_snapshot для быстрого показа."""
    doll.stats_snapshot = calculate_doll_stats(doll)
    doll.save(update_fields=['stats_snapshot', 'updated_at'])


def get_active_effects(doll):
    """
    Собирает активные эффекты куклы:
    - от духа-хранителя (если надет)
    - от бонусов сетов (если набрано нужное количество предметов)
    Возвращает список dict {source, name, description}.
    """
    from catalog.models import SetBonus
    effects = []

    # Считаем предметы по сетам и собираем эффект духа
    set_counts = defaultdict(int)
    for doll_slot in doll.slots.select_related('item__item_set', 'item__effect').all():
        if not doll_slot.item:
            continue
        # Эффект духа-хранителя
        if doll_slot.slot_type == 'guardian' and doll_slot.item.effect:
            eff = doll_slot.item.effect
            effects.append({
                'source': f'Дух: {doll_slot.item.name}',
                'name': eff.name,
                'description': eff.description,
            })
        if doll_slot.item.item_set_id:
            set_counts[doll_slot.item.item_set_id] += 1

    # Эффекты от сетов
    for set_id, count in set_counts.items():
        bonuses = SetBonus.objects.filter(
            item_set_id=set_id,
            pieces_required__lte=count,
            effect__isnull=False,
        ).select_related('effect', 'item_set')
        for bonus in bonuses:
            effects.append({
                'source': f'Сет: {bonus.item_set.name} ({bonus.pieces_required} пред.)',
                'name': bonus.effect.name,
                'description': bonus.effect.description,
            })

    return effects


def save_doll_state(doll):
    """Сохраняет полное состояние куклы в saved_state."""
    slots = {}
    for ds in doll.slots.select_related('item').prefetch_related('custom_stats__stat').all():
        slots[ds.slot_type] = {
            'item_id': ds.item_id,
            'stats': {cs.stat_id: cs.value for cs in ds.custom_stats.all()}
        }
    skills = {
        str(sp.node_id): sp.points_invested
        for sp in doll.skill_points.all()
    }
    doll.saved_state = {
        'character_level': doll.character_level,
        'slots': slots,
        'skills': skills,
    }
    doll.save(update_fields=['saved_state'])


def restore_doll_state(doll):
    """Восстанавливает состояние куклы из saved_state."""
    from catalog.models import Item
    from .models import DollSlot, DollSlotStat, DollSkill
    from skills.models import SkillNode

    state = doll.saved_state
    if not state:
        return False

    # Уровень
    doll.character_level = state.get('character_level', 1)
    doll.save(update_fields=['character_level'])

    # Слоты
    for slot_type, slot_data in state.get('slots', {}).items():
        ds, _ = DollSlot.objects.get_or_create(doll=doll, slot_type=slot_type)
        item_id = slot_data.get('item_id')
        ds.item_id = item_id
        ds.save(update_fields=['item'])
        ds.custom_stats.all().delete()
        for stat_id, value in slot_data.get('stats', {}).items():
            DollSlotStat.objects.create(doll_slot=ds, stat_id=int(stat_id), value=value)

    # Навыки
    doll.skill_points.all().delete()
    for node_id, points in state.get('skills', {}).items():
        if points > 0:
            try:
                node = SkillNode.objects.get(pk=int(node_id))
                DollSkill.objects.create(doll=doll, node=node, points_invested=points)
            except SkillNode.DoesNotExist:
                pass

    save_stats_snapshot(doll)
    return True


def build_index_context(request, doll, user_dolls, slot, settings):
    """Собирает контекст для главной страницы калькулятора."""
    from catalog.models import Stat, ItemSet, Rarity, Item, SlotType
    from skills.models import SkillNode, SkillEdge
    import json

    doll_slots = {
        ds.slot_type: ds
        for ds in doll.slots.select_related('item').prefetch_related('custom_stats__stat').all()
    }
    grouped_stats = get_stats_grouped(doll)
    available_points = get_available_points(doll)
    active_effects = get_active_effects(doll)

    skill_nodes = SkillNode.objects.prefetch_related('bonuses__stat', 'edges_to').order_by('order', 'branch')
    skill_edges = SkillEdge.objects.select_related('from_node', 'to_node').all()
    invested_map = {ds.node_id: ds.points_invested for ds in doll.skill_points.all()}

    items_by_slot = {}
    for slot_type, _ in SlotType.choices:
        items_by_slot[slot_type] = list(
            Item.objects.filter(slot_type=slot_type, is_active=True).values('id', 'name', 'rarity')
        )

    all_stats = list(Stat.objects.values('id', 'name_ru', 'slug', 'category', 'is_percent').order_by('order'))

    rarity_order = [r.value for r in [
        Rarity.LEGENDARY, Rarity.LIMITED, Rarity.CRAFTED,
        Rarity.EPIC, Rarity.RARE, Rarity.UNCOMMON, Rarity.COMMON
    ]]
    rarity_labels = dict(Rarity.choices)
    sets_by_rarity = []
    for rarity in rarity_order:
        sets = ItemSet.objects.filter(rarity=rarity).prefetch_related('items')
        set_list = []
        for s in sets:
            items_in_set = []
            for it in s.items.filter(is_active=True):
                items_in_set.append({
                    'id': it.id, 'name': it.name, 'slot_type': it.slot_type,
                    'rarity': it.rarity,
                    'image_url': it.image.url if it.image and it.image.name else None,
                })
            if items_in_set:
                set_list.append({'id': s.id, 'name': s.name, 'items': items_in_set})
        if set_list:
            sets_by_rarity.append({'rarity': rarity, 'label': rarity_labels.get(rarity, rarity), 'sets': set_list})

    no_set_items = []
    for it in Item.objects.filter(item_set__isnull=True, is_active=True).order_by('rarity', 'name'):
        no_set_items.append({
            'id': it.id, 'name': it.name, 'slot_type': it.slot_type, 'rarity': it.rarity,
            'image_url': it.image.url if it.image and it.image.name else None,
        })

    skill_nodes_data = []
    for node in skill_nodes:
        bonuses = [{'stat_slug': b.stat.slug, 'v1': b.value_level_1, 'v2': b.value_level_2, 'v3': b.value_level_3}
                   for b in node.bonuses.all()]
        skill_nodes_data.append({'id': node.pk, 'branch': node.branch, 'order': node.order,
                                  'max_points': node.max_points, 'bonuses': bonuses})

    return {
        'doll': doll,
        'doll_slots': doll_slots,
        'slot_types': SlotType.choices,
        'grouped_stats': grouped_stats,
        'available_points': available_points,
        'is_over_budget': is_over_budget(doll),
        'active_effects': active_effects,
        'skill_nodes': skill_nodes,
        'skill_edges': skill_edges,
        'invested_map': invested_map,
        'items_by_slot': json.dumps(items_by_slot),
        'all_stats': json.dumps(all_stats),
        'sets_by_rarity': json.dumps(sets_by_rarity),
        'no_set_items': json.dumps(no_set_items),
        'skill_nodes_data': json.dumps(skill_nodes_data),
        'base_character_stats': json.dumps(settings.BASE_CHARACTER_STATS),
        'user_dolls': user_dolls,
        'active_slot': slot,
        'doll_slots_count': settings.DOLL_SLOTS_PER_USER,
    }


def restore_doll_from_snapshot(target, state):
    """Восстанавливает куклу из состояния снапшота."""
    from .models import DollSlot, DollSlotStat, DollSkill
    from skills.models import SkillNode

    target.character_level = state.get('character_level', 1)
    target.save(update_fields=['character_level'])

    for slot_type, slot_data in state.get('slots', {}).items():
        tgt_slot, _ = DollSlot.objects.get_or_create(doll=target, slot_type=slot_type)
        tgt_slot.item_id = slot_data.get('item_id')
        tgt_slot.save(update_fields=['item'])
        tgt_slot.custom_stats.all().delete()
        for stat_id, value in slot_data.get('stats', {}).items():
            DollSlotStat.objects.create(doll_slot=tgt_slot, stat_id=int(stat_id), value=value)

    target.skill_points.all().delete()
    for node_id, points in state.get('skills', {}).items():
        if points > 0:
            try:
                node = SkillNode.objects.get(pk=int(node_id))
                DollSkill.objects.create(doll=target, node=node, points_invested=points)
            except SkillNode.DoesNotExist:
                pass

    save_stats_snapshot(target)


def build_doll_snapshot_state(doll):
    """Собирает состояние куклы для снапшота."""
    slots = {}
    for ds in doll.slots.select_related('item').prefetch_related('custom_stats__stat').all():
        slots[ds.slot_type] = {
            'item_id': ds.item_id,
            'stats': {str(cs.stat_id): cs.value for cs in ds.custom_stats.all()}
        }
    skills = {str(sp.node_id): sp.points_invested for sp in doll.skill_points.all()}
    return {
        'character_level': doll.character_level,
        'slots': slots,
        'skills': skills,
        'doll_name': doll.name,
    }