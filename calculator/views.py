import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.conf import settings

from catalog.models import Item, SlotType, Stat
from skills.models import SkillNode, SkillEdge
from .models import Doll, DollSlot, DollSlotStat, DollSkill
from .services import (
    get_stats_grouped, get_available_points, get_total_points,
    get_spent_points, is_over_budget,
    can_unlock_node, can_remove_point, save_stats_snapshot,
    calculate_doll_stats, get_active_effects,
    save_doll_state, restore_doll_state
)


def _get_or_create_session_doll(request):
    doll_id = request.session.get('guest_doll_id')
    if doll_id:
        try:
            return Doll.objects.get(pk=doll_id, owner=None)
        except Doll.DoesNotExist:
            pass
    doll = Doll.objects.create(owner=None)
    for slot_type, _ in SlotType.choices:
        DollSlot.objects.create(doll=doll, slot_type=slot_type)
    request.session['guest_doll_id'] = doll.pk
    return doll


def _get_user_doll(request, slot_order=0):
    doll, created = Doll.objects.get_or_create(
        owner=request.user,
        slot_order=slot_order,
        defaults={'name': f'Кукла {slot_order + 1}'},
    )
    if created:
        for slot_type, _ in SlotType.choices:
            DollSlot.objects.create(doll=doll, slot_type=slot_type)
    return doll

def _get_or_create_comparison_doll(request):
    """Кукла сравнения — гостевая, живёт в сессии. Старые чистим (>2 дней)."""
    from django.utils import timezone
    from datetime import timedelta

    # Чистим старые куклы сравнения (старше 2 дней)
    Doll.objects.filter(
        owner=None,
        name='__comparison__',
        updated_at__lt=timezone.now() - timedelta(days=2)
    ).delete()

    doll_id = request.session.get('comparison_doll_id')
    if doll_id:
        try:
            return Doll.objects.get(pk=doll_id, owner=None, name='__comparison__')
        except Doll.DoesNotExist:
            pass

    doll = Doll.objects.create(owner=None, name='__comparison__')
    for slot_type, _ in SlotType.choices:
        DollSlot.objects.create(doll=doll, slot_type=slot_type)
    request.session['comparison_doll_id'] = doll.pk
    return doll


def _get_doll(request, doll_id=None):
    """Получить куклу для текущего пользователя или гостя."""
    comp_id = request.session.get('comparison_doll_id')

    # Если запрашивается кукла сравнения — она всегда owner=None
    if doll_id and comp_id and int(doll_id) == comp_id:
        return get_object_or_404(Doll, pk=doll_id, owner=None, name='__comparison__')

    if request.user.is_authenticated:
        return get_object_or_404(Doll, pk=doll_id, owner=request.user)
    else:
        if doll_id:
            guest_id = request.session.get('guest_doll_id')
            if guest_id and int(doll_id) == guest_id:
                return get_object_or_404(Doll, pk=doll_id, owner=None)
        guest_id = request.session.get('guest_doll_id')
        return get_object_or_404(Doll, pk=guest_id, owner=None)


def index(request):
    return _render_index(request)


def _render_index(request):
    """Основная логика рендера калькулятора."""
    if request.user.is_authenticated:
        slot = int(request.GET.get('slot', 0))
        slot = max(0, min(slot, settings.DOLL_SLOTS_PER_USER - 1))
        doll = _get_user_doll(request, slot)
        user_dolls = Doll.objects.filter(owner=request.user).order_by('slot_order')
    else:
        doll = _get_or_create_session_doll(request)
        user_dolls = []
        slot = None

    doll_slots = {
        ds.slot_type: ds
        for ds in doll.slots.select_related('item').prefetch_related('custom_stats__stat').all()
    }

    grouped_stats = get_stats_grouped(doll)
    available_points = get_available_points(doll)

    skill_nodes = SkillNode.objects.prefetch_related('bonuses__stat', 'edges_to').order_by('order', 'branch')
    skill_edges = SkillEdge.objects.select_related('from_node', 'to_node').all()
    invested_map = {
        ds.node_id: ds.points_invested
        for ds in doll.skill_points.all()
    }

    items_by_slot = {}
    for slot_type, _ in SlotType.choices:
        items_by_slot[slot_type] = list(
            Item.objects.filter(slot_type=slot_type, is_active=True).values('id', 'name', 'rarity')
        )

    from catalog.models import Stat, ItemSet, Rarity
    all_stats = list(Stat.objects.values('id', 'name_ru', 'slug', 'category', 'is_percent').order_by('order'))

    # Сеты сгруппированные по редкости сета (по убыванию)
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
                    'id': it.id,
                    'name': it.name,
                    'slot_type': it.slot_type,
                    'rarity': it.rarity,
                    'image_url': it.image.url if it.image and it.image.name else None,
                })
            if items_in_set:
                set_list.append({'id': s.id, 'name': s.name, 'items': items_in_set})
        if set_list:
            sets_by_rarity.append({
                'rarity': rarity,
                'label': rarity_labels.get(rarity, rarity),
                'sets': set_list,
            })

    # Предметы без сета
    no_set_items = []
    for it in Item.objects.filter(item_set__isnull=True, is_active=True).order_by('rarity', 'name'):
        no_set_items.append({
            'id': it.id,
            'name': it.name,
            'slot_type': it.slot_type,
            'rarity': it.rarity,
            'image_url': it.image.url if it.image and it.image.name else None,
        })

    # Данные узлов навыков с бонусами для JS расчёта
    skill_nodes_data = []
    for node in skill_nodes:
        bonuses = []
        for b in node.bonuses.all():
            bonuses.append({
                'stat_slug': b.stat.slug,
                'v1': b.value_level_1,
                'v2': b.value_level_2,
                'v3': b.value_level_3,
            })
        skill_nodes_data.append({
            'id': node.pk,
            'branch': node.branch,
            'order': node.order,
            'max_points': node.max_points,
            'bonuses': bonuses,
        })

    context = {
        'doll': doll,
        'doll_slots': doll_slots,
        'slot_types': SlotType.choices,
        'grouped_stats': grouped_stats,
        'available_points': available_points,
        'is_over_budget': is_over_budget(doll),
        'active_effects': get_active_effects(doll),
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
    return render(request, 'calculator/index.html', context)


def doll_public(request, uuid):
    """Открыть снимок куклы по ссылке."""
    from .models import DollSnapshot
    snapshot = get_object_or_404(DollSnapshot, uuid=uuid)
    state = snapshot.state

    # Определяем целевую куклу
    if request.user.is_authenticated:
        slot = int(request.GET.get('slot', 0))
        slot = max(0, min(slot, settings.DOLL_SLOTS_PER_USER - 1))
        target = _get_user_doll(request, slot)
    else:
        target = _get_or_create_session_doll(request)

    # Восстанавливаем из снимка
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
                from skills.models import SkillNode
                node = SkillNode.objects.get(pk=int(node_id))
                DollSkill.objects.create(doll=target, node=node, points_invested=points)
            except Exception:
                pass

    save_stats_snapshot(target)
    return _render_index(request)


@require_POST
def api_select_item(request):
    """API: выбрать предмет в слот. Копирует базовые статы как кастомные."""
    data = json.loads(request.body)
    doll = _get_doll(request, data.get('doll_id'))
    slot_type = data.get('slot_type')
    item_id = data.get('item_id')

    doll_slot = get_object_or_404(DollSlot, doll=doll, slot_type=slot_type)

    if not item_id:
        # Снять предмет
        doll_slot.item = None
        doll_slot.save()
        doll_slot.custom_stats.all().delete()
    else:
        item = get_object_or_404(Item, pk=item_id, slot_type=slot_type)
        # Если предмет сменился — чистим старые статы
        if doll_slot.item_id != item.pk:
            doll_slot.custom_stats.all().delete()
        doll_slot.item = item
        doll_slot.save()
        # Копируем базовые статы нового предмета (если ещё нет)
        existing_stat_ids = set(doll_slot.custom_stats.values_list('stat_id', flat=True))
        for item_stat in item.stats.select_related('stat').all():
            if item_stat.stat_id not in existing_stat_ids:
                DollSlotStat.objects.create(
                    doll_slot=doll_slot,
                    stat=item_stat.stat,
                    value=item_stat.base_value,
                )

    fresh_doll = Doll.objects.get(pk=doll.pk)
    save_stats_snapshot(fresh_doll)

    # Возвращаем статы слота для модалки
    slot_stats = []
    if doll_slot.item:
        for entry in doll_slot.get_stats_with_diff():
            slot_stats.append({
                'stat_id': entry['stat'].pk,
                'stat_slug': entry['stat'].slug,
                'stat_name': entry['stat'].name_ru,
                'is_percent': entry['stat'].is_percent,
                'base_value': entry['base_value'],
                'custom_value': entry['custom_value'],
                'diff_pct': entry['diff_pct'],
            })

    return JsonResponse({
        'ok': True,
        'stats': calculate_doll_stats(fresh_doll),
        'effects': get_active_effects(fresh_doll),
        'slot_stats': slot_stats,
        'item_name': doll_slot.item.name if doll_slot.item else None,
        'item_rarity': doll_slot.item.rarity if doll_slot.item else None,
        'image_url': doll_slot.item.image.url if doll_slot.item and doll_slot.item.image and doll_slot.item.image.name else None,
    })


@require_POST
def api_get_slot_stats(request):
    """API: получить статы слота для редактирования."""
    data = json.loads(request.body)
    doll = _get_doll(request, data.get('doll_id'))
    slot_type = data.get('slot_type')
    doll_slot = get_object_or_404(DollSlot, doll=doll, slot_type=slot_type)

    slot_stats = []
    if doll_slot.item:
        for entry in doll_slot.get_stats_with_diff():
            slot_stats.append({
                'stat_id': entry['stat'].pk,
                'stat_slug': entry['stat'].slug,
                'stat_name': entry['stat'].name_ru,
                'is_percent': entry['stat'].is_percent,
                'base_value': entry['base_value'],
                'custom_value': entry['custom_value'],
                'diff_pct': entry['diff_pct'],
            })

    return JsonResponse({
        'ok': True,
        'slot_stats': slot_stats,
        'item_name': doll_slot.item.name if doll_slot.item else '',
        'item_rarity': doll_slot.item.rarity if doll_slot.item else '',
    })


@require_POST
def api_save_slot_stats(request):
    """API: сохранить кастомные статы слота."""
    data = json.loads(request.body)
    doll = _get_doll(request, data.get('doll_id'))
    slot_type = data.get('slot_type')
    new_stats = data.get('stats', {})  # {stat_id: value}

    doll_slot = get_object_or_404(DollSlot, doll=doll, slot_type=slot_type)

    for stat_id, value in new_stats.items():
        value = max(0, float(value))  # только положительные
        DollSlotStat.objects.update_or_create(
            doll_slot=doll_slot,
            stat_id=int(stat_id),
            defaults={'value': value},
        )

    fresh_doll = Doll.objects.get(pk=doll.pk)
    save_stats_snapshot(fresh_doll)

    return JsonResponse({
        'ok': True,
        'stats': calculate_doll_stats(fresh_doll),
        'effects': get_active_effects(fresh_doll),
    })


@require_POST
def api_update_skill(request):
    data = json.loads(request.body)
    doll = _get_doll(request, data.get('doll_id'))
    node_id = data.get('node_id')
    action = data.get('action', 'add')
    node = get_object_or_404(SkillNode, pk=node_id)
    doll_skill, _ = DollSkill.objects.get_or_create(doll=doll, node=node)

    if action == 'add':
        if not can_unlock_node(doll, node):
            return JsonResponse({'ok': False, 'error': 'Не разблокировано'}, status=400)
        if get_available_points(doll) <= 0:
            return JsonResponse({'ok': False, 'error': 'Нет очков'}, status=400)
        if doll_skill.points_invested < node.max_points:
            doll_skill.points_invested += 1
            doll_skill.save()
    elif action == 'remove':
        if doll_skill.points_invested > 0:
            if not can_remove_point(doll, node):
                return JsonResponse({'ok': False, 'error': 'Сначала откатите зависимые навыки'}, status=400)
            doll_skill.points_invested -= 1
            doll_skill.save()

    fresh_doll = Doll.objects.get(pk=doll.pk)
    save_stats_snapshot(fresh_doll)
    stats = calculate_doll_stats(fresh_doll)

    return JsonResponse({
        'ok': True,
        'invested': doll_skill.points_invested,
        'available_points': get_available_points(fresh_doll),
        'stats': stats,
    })


@require_POST
def api_reset_skills(request):
    data = json.loads(request.body)
    doll = _get_doll(request, data.get('doll_id'))
    doll.skill_points.all().update(points_invested=0)
    fresh_doll = Doll.objects.get(pk=doll.pk)
    save_stats_snapshot(fresh_doll)
    return JsonResponse({
        'ok': True,
        'available_points': get_available_points(fresh_doll),
        'stats': calculate_doll_stats(fresh_doll),
    })


@require_POST
@login_required
def api_save_doll(request):
    """API: сохранить куклу — записывает полное состояние."""
    data = json.loads(request.body)
    doll = get_object_or_404(Doll, pk=data.get('doll_id'), owner=request.user)
    name = data.get('name', '').strip()
    if name:
        doll.name = name[:64]
        doll.save(update_fields=['name'])
    save_doll_state(doll)
    save_stats_snapshot(doll)
    return JsonResponse({
        'ok': True,
        'public_url': request.build_absolute_uri(doll.get_absolute_url()),
    })


@require_POST
def api_set_level(request):
    data = json.loads(request.body)
    doll = _get_doll(request, data.get('doll_id'))
    level = int(data.get('level', 1))
    doll.character_level = max(1, min(200, level))
    doll.save(update_fields=['character_level'])
    fresh_doll = Doll.objects.get(pk=doll.pk)
    return JsonResponse({
        'ok': True,
        'available_points': get_available_points(fresh_doll),
        'is_over_budget': is_over_budget(fresh_doll),
    })


@require_POST
def api_equip_set(request):
    """API: надеть все предметы сета сразу."""
    data = json.loads(request.body)
    doll = _get_doll(request, data.get('doll_id'))
    set_id = data.get('set_id')

    from catalog.models import ItemSet
    item_set = get_object_or_404(ItemSet, pk=set_id)

    equipped = []
    for item in item_set.items.filter(is_active=True):
        doll_slot = DollSlot.objects.filter(doll=doll, slot_type=item.slot_type).first()
        if not doll_slot:
            continue
        doll_slot.item = item
        doll_slot.save()
        # Копируем базовые статы
        doll_slot.custom_stats.all().delete()
        for item_stat in item.stats.select_related('stat').all():
            DollSlotStat.objects.create(
                doll_slot=doll_slot,
                stat=item_stat.stat,
                value=item_stat.base_value,
            )
        equipped.append({'slot_type': item.slot_type, 'item_name': item.name,
                         'item_rarity': item.rarity,
                         'image_url': item.image.url if item.image else None})

    fresh_doll = Doll.objects.get(pk=doll.pk)
    save_stats_snapshot(fresh_doll)

    return JsonResponse({
        'ok': True,
        'stats': calculate_doll_stats(fresh_doll),
        'effects': get_active_effects(fresh_doll),
        'equipped': equipped,
    })


@require_POST
def api_get_item_stats(request):
    """API: получить базовые статы предмета для куклы сравнения."""
    import json as _json
    data = _json.loads(request.body)
    item_id = data.get('item_id')
    from catalog.models import Item
    item = get_object_or_404(Item, pk=item_id)
    stats = {s.stat.slug: s.base_value for s in item.stats.select_related('stat').all()}
    return JsonResponse({
        'ok': True,
        'item_name': item.name,
        'rarity': item.rarity,
        'set_id': item.item_set_id,
        'image_url': item.image.url if item.image and item.image.name else None,
        'stats': stats,
    })


@require_POST
def api_get_comparison_doll(request):
    """API: получить или создать куклу сравнения."""
    doll = _get_or_create_comparison_doll(request)
    fresh_doll = Doll.objects.get(pk=doll.pk)

    from .services import calculate_doll_stats, get_available_points
    doll_slots = {}
    for ds in fresh_doll.slots.select_related('item').prefetch_related('custom_stats__stat').all():
        doll_slots[ds.slot_type] = {
            'item_id': ds.item_id,
            'item_name': ds.item.name if ds.item else None,
            'item_rarity': ds.item.rarity if ds.item else None,
            'image_url': ds.item.image.url if ds.item and ds.item.image and ds.item.image.name else None,
        }

    invested_map = {
        ds.node_id: ds.points_invested
        for ds in fresh_doll.skill_points.all()
    }

    return JsonResponse({
        'ok': True,
        'doll_id': fresh_doll.pk,
        'level': fresh_doll.character_level,
        'stats': calculate_doll_stats(fresh_doll),
        'available_points': get_available_points(fresh_doll),
        'slots': doll_slots,
        'invested_map': invested_map,
    })


@require_POST
@login_required
def api_copy_doll(request):
    """API: сохранить текущую (временную или обычную) куклу в слот пользователя."""
    data = json.loads(request.body)
    slot_order = int(data.get('slot_order', 0))
    source_id = data.get('doll_id')

    source = get_object_or_404(Doll, pk=source_id)

    target, created = Doll.objects.get_or_create(
        owner=request.user,
        slot_order=slot_order,
        defaults={'name': source.name if source.name != '__temp__' else 'Кукла ' + str(slot_order + 1)},
    )
    if not created:
        target.name = source.name if source.name != '__temp__' else target.name
        target.character_level = source.character_level
        target.save()

    if created:
        for slot_type, _ in SlotType.choices:
            DollSlot.objects.create(doll=target, slot_type=slot_type)

    for src_slot in source.slots.select_related('item').prefetch_related('custom_stats__stat').all():
        tgt_slot, _ = DollSlot.objects.get_or_create(doll=target, slot_type=src_slot.slot_type)
        tgt_slot.item = src_slot.item
        tgt_slot.save()
        tgt_slot.custom_stats.all().delete()
        for cs in src_slot.custom_stats.all():
            DollSlotStat.objects.create(doll_slot=tgt_slot, stat=cs.stat, value=cs.value)

    target.skill_points.all().delete()
    for sp in source.skill_points.all():
        DollSkill.objects.create(doll=target, node=sp.node, points_invested=sp.points_invested)

    target.character_level = source.character_level
    save_stats_snapshot(target)

    return JsonResponse({'ok': True, 'slot_order': slot_order})


@require_POST
@login_required
def api_load_doll(request):
    """API: загрузить сохранённое состояние куклы."""
    data = json.loads(request.body)
    doll = get_object_or_404(Doll, pk=data.get('doll_id'), owner=request.user)
    if not doll.saved_state:
        return JsonResponse({'ok': False, 'error': 'Нет сохранённого состояния'})
    restored = restore_doll_state(doll)
    if restored:
        fresh = Doll.objects.get(pk=doll.pk)
        return JsonResponse({'ok': True, 'redirect': f'/?slot={doll.slot_order}'})
    return JsonResponse({'ok': False, 'error': 'Ошибка восстановления'})


@require_POST
@login_required
def api_create_snapshot(request):
    """API: создать снимок куклы для публичной ссылки."""
    data = json.loads(request.body)
    doll = get_object_or_404(Doll, pk=data.get('doll_id'), owner=request.user)

    # Собираем текущее состояние
    slots = {}
    for ds in doll.slots.select_related('item').prefetch_related('custom_stats__stat').all():
        slots[ds.slot_type] = {
            'item_id': ds.item_id,
            'stats': {str(cs.stat_id): cs.value for cs in ds.custom_stats.all()}
        }
    skills = {
        str(sp.node_id): sp.points_invested
        for sp in doll.skill_points.all()
    }
    state = {
        'character_level': doll.character_level,
        'slots': slots,
        'skills': skills,
        'doll_name': doll.name,
    }

    from .models import DollSnapshot
    snapshot = DollSnapshot.objects.create(doll=doll, state=state)

    return JsonResponse({
        'ok': True,
        'url': request.build_absolute_uri(f'/share/{snapshot.uuid}/'),
    })