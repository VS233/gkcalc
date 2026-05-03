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