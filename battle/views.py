import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from calculator.models import Doll
from calculator.services import calculate_doll_stats
from .engine import simulate_battle


def _check_premium(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Требуется авторизация'}, status=403)
    if not request.user.is_premium:
        return JsonResponse({'ok': False, 'error': 'Требуется Премиум доступ'}, status=403)
    return None


@require_POST
def api_simulate(request):
    """API: симуляция боя между основной куклой и куклой сравнения."""
    err = _check_premium(request)
    if err:
        return err

    data = json.loads(request.body)
    doll_a_id = data.get('doll_a_id')
    doll_b_id = data.get('doll_b_id')
    rounds = min(int(data.get('rounds', 10)), 100)

    try:
        doll_a = Doll.objects.get(pk=doll_a_id, owner=request.user)
    except Doll.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Кукла не найдена'}, status=404)

    # Кукла сравнения — гостевая
    comp_id = request.session.get('comparison_doll_id')
    if not comp_id or int(doll_b_id) != comp_id:
        return JsonResponse({'ok': False, 'error': 'Кукла сравнения не найдена'}, status=404)

    try:
        doll_b = Doll.objects.get(pk=doll_b_id, owner=None, name='__comparison__')
    except Doll.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Кукла сравнения не найдена'}, status=404)

    stats_a = calculate_doll_stats(doll_a)
    stats_b = calculate_doll_stats(doll_b)

    result = simulate_battle(stats_a, stats_b, rounds)
    result['ok'] = True
    result['stats_a'] = stats_a
    result['stats_b'] = stats_b

    return JsonResponse(result)