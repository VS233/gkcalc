"""
Движок симуляции боя.
Формулы:
- Урон = max(1, атака - защита) * базовый_урон (100)
- Если защита >> атака: урон стремится к 1-2
- Крит: шанс крита → урон * (1 + крит_урон/100)
- Чистый урон: шанс чист → +чист_урон (игнорирует защиту)
- Уклонение: шанс уклониться от атаки (кап 80%)
- Точность снижает уклонение противника
- Вампиризм: восстанавливает HP = урон * вампиризм%
- Отражение: возвращает атакующему урон * отражение%
- Антагонисты: уклонение vs точность, вампиризм vs сопр.вампиризму
"""
import random

EVASION_CAP = 0.85  # максимальный уворот 85%
BASE_DAMAGE = 100   # базовый урон


def _calc_damage(attacker: dict, defender: dict) -> dict:
    """Считает урон одной атаки. Возвращает dict с деталями."""
    result = {
        'evaded': False,
        'crit': False,
        'pure': False,
        'damage': 0,
        'reflected': 0,
        'healed': 0,
    }

    # Уклонение vs точность
    evasion = min(defender.get('evasion', 0) / 100, EVASION_CAP)
    accuracy = attacker.get('accuracy', 100) / 100
    # Точность снижает эффективное уклонение
    effective_evasion = max(0, evasion - (accuracy - 1.0))
    if random.random() < effective_evasion:
        result['evaded'] = True
        return result

    # Базовый урон с учётом атаки и защиты
    attack = attacker.get('attack', 0)
    defense = defender.get('defense', 0)
    ratio = attack / max(defense, 1)
    if ratio >= 1:
        raw_damage = BASE_DAMAGE + (attack - defense)
    else:
        # Защита сильно превышает атаку — урон падает
        raw_damage = max(1, BASE_DAMAGE * (ratio ** 2))

    damage = raw_damage

    # Крит
    crit_chance = attacker.get('crit_chance', 0) / 100
    if random.random() < crit_chance:
        result['crit'] = True
        crit_mult = 1 + attacker.get('crit_damage', 125) / 100
        damage *= crit_mult

    # Чистый урон (игнорирует защиту, добавляется отдельно)
    pure_chance = attacker.get('pure_chance', 0) / 100
    if random.random() < pure_chance:
        result['pure'] = True
        damage += attacker.get('pure_damage', 0)

    damage = max(1, round(damage))
    result['damage'] = damage

    # Отражение (антагонист вампиризма)
    reflection = defender.get('reflection', 0) / 100
    result['reflected'] = round(damage * reflection)

    # Вампиризм (антагонист сопр.вампиризму)
    vampirism = attacker.get('vampirism', 0) / 100
    res_vamp = defender.get('res_vampirism', 0) / 100
    effective_vamp = max(0, vampirism - res_vamp)
    result['healed'] = round(damage * effective_vamp)

    return result


def simulate_battle(stats_a: dict, stats_b: dict, rounds: int = 10) -> dict:
    """
    Симулирует N боёв между двумя куклами.
    stats_a, stats_b — словари статов {slug: value}
    Возвращает результаты и статистику.
    """
    wins_a = 0
    wins_b = 0
    battle_log = []

    for battle_num in range(1, rounds + 1):
        hp_a = stats_a.get('health', 100)
        hp_b = stats_b.get('health', 100)
        max_hp_a = hp_a
        max_hp_b = hp_b
        turn = 0
        max_turns = 100  # защита от бесконечного боя

        while hp_a > 0 and hp_b > 0 and turn < max_turns:
            turn += 1
            # A атакует B
            hit = _calc_damage(stats_a, stats_b)
            if not hit['evaded']:
                hp_b -= hit['damage']
                hp_a -= hit['reflected']
                hp_a = min(max_hp_a, hp_a + hit['healed'])

            if hp_b <= 0:
                break

            # B атакует A
            hit2 = _calc_damage(stats_b, stats_a)
            if not hit2['evaded']:
                hp_a -= hit2['damage']
                hp_b -= hit2['reflected']
                hp_b = min(max_hp_b, hp_b + hit2['healed'])

        if hp_a > hp_b:
            winner = 'a'
            wins_a += 1
        elif hp_b > hp_a:
            winner = 'b'
            wins_b += 1
        else:
            winner = 'draw'

        battle_log.append({
            'battle': battle_num,
            'winner': winner,
            'hp_a_left': max(0, round(hp_a)),
            'hp_b_left': max(0, round(hp_b)),
            'turns': turn,
        })

    total = wins_a + wins_b or 1
    return {
        'wins_a': wins_a,
        'wins_b': wins_b,
        'draws': rounds - wins_a - wins_b,
        'win_rate_a': round(wins_a / rounds * 100),
        'win_rate_b': round(wins_b / rounds * 100),
        'log': battle_log,
    }