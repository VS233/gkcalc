"""
Движок симуляции боя.
Формулы:
- Базовый урон 100 единиц
- Урон = BASE_DAMAGE + (атака - защита) если атака >= защита
- Если защита >> атака: урон = max(1, BASE_DAMAGE * ratio²)
- Крит: шанс крита → урон * (1 + крит_урон/100)
- Чистый урон: шанс чист → +чист_урон (игнорирует защиту)
- Уклонение: кап 85%, точность снижает уклонение противника
- Вампиризм: восстанавливает HP = урон * вампиризм% (антагонист: сопр.вампиризму)
- Отражение: возвращает атакующему урон * отражение%
- Антагонисты: уклонение vs точность, вампиризм vs сопр.вампиризму
- Макс. раундов в бою: 25
- Победитель — у кого больше HP в конце 25 раундов
- Ничья — одинаковое HP или оба погибли одновременно (отражение)
- Первым бьёт основная кукла (A)
"""
import random

EVASION_CAP = 0.85  # максимальный уворот 85%
BASE_DAMAGE = 100   # базовый урон
MAX_TURNS = 25      # максимум раундов в одном бою


def _calc_damage(attacker: dict, defender: dict) -> dict:
    """Считает урон одной атаки. Возвращает dict с деталями."""
    result = {'evaded': False, 'crit': False, 'pure': False,
              'damage': 0, 'reflected': 0, 'healed': 0}

    # Уклонение vs точность
    evasion = min(defender.get('evasion', 0) / 100, EVASION_CAP)
    accuracy_bonus = (attacker.get('accuracy', 100) - 100) / 100
    effective_evasion = min(1.0, max(0, evasion - accuracy_bonus))
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
        # Защита сильно превышает атаку — урон падает квадратично
        raw_damage = max(1, BASE_DAMAGE * (ratio ** 2))
    damage = raw_damage

    # Крит
    if random.random() < attacker.get('crit_chance', 0) / 100:
        result['crit'] = True
        damage *= 1 + attacker.get('crit_damage', 125) / 100

    # Чистый урон (игнорирует защиту, добавляется отдельно)
    if random.random() < attacker.get('pure_chance', 0) / 100:
        result['pure'] = True
        damage += attacker.get('pure_damage', 0)

    damage = max(1, round(damage))
    result['damage'] = damage

    # Отражение — возвращает часть урона атакующему
    result['reflected'] = round(damage * defender.get('reflection', 0) / 100)

    # Вампиризм — восстановление HP атакующего (снижается сопр.вампиризму)
    effective_vamp = max(0, attacker.get('vampirism', 0) / 100 - defender.get('res_vampirism', 0) / 100)
    result['healed'] = round(damage * effective_vamp)

    return result


def _format_action(name: str, hit: dict) -> str:
    """Форматирует строку действия для лога раунда."""
    if hit['evaded']:
        return f"{name}: промах (уклонение)"

    parts = [f"{hit['damage']} урона"]
    mods = []
    if hit['crit']: mods.append("крит")
    if hit['pure']: mods.append("чистый удар")
    if mods: parts[0] += f" ({', '.join(mods)})"
    if hit['reflected'] > 0: parts.append(f"отражено {hit['reflected']}")
    if hit['healed'] > 0: parts.append(f"восст. {hit['healed']} HP")

    return f"{name}: {', '.join(parts)}"


def simulate_battle(stats_a: dict, stats_b: dict, rounds: int = 10) -> dict:
    """
    Симулирует N боёв между двумя куклами.
    stats_a, stats_b — словари статов {slug: value}
    Возвращает результаты, статистику и подробный лог каждого боя.
    """
    wins_a = wins_b = draws = 0
    battle_log = []

    for battle_num in range(1, rounds + 1):
        hp_a = stats_a.get('health', 100)
        hp_b = stats_b.get('health', 100)
        max_hp_a, max_hp_b = hp_a, hp_b
        turn_log = []

        for turn in range(1, MAX_TURNS + 1):
            turn_lines = []

            # Основная кукла (A) атакует первой
            hit_a = _calc_damage(stats_a, stats_b)
            if not hit_a['evaded']:
                hp_b -= hit_a['damage']
                hp_a -= hit_a['reflected']
                hp_a = min(max_hp_a, hp_a + hit_a['healed'])
            turn_lines.append(_format_action("Ваша атака", hit_a))

            # Оба погибли одновременно (отражение убило A) — ничья
            if hp_a <= 0 and hp_b <= 0:
                turn_log.append({'turn': turn, 'lines': turn_lines})
                break

            # B погиб — A победила, раунд заканчивается одной строкой
            if hp_b <= 0:
                turn_log.append({'turn': turn, 'lines': turn_lines})
                break

            # Кукла сравнения (B) атакует
            hit_b = _calc_damage(stats_b, stats_a)
            if not hit_b['evaded']:
                hp_a -= hit_b['damage']
                hp_b -= hit_b['reflected']
                hp_b = min(max_hp_b, hp_b + hit_b['healed'])
            turn_lines.append(_format_action("Кукла сравнения атакует", hit_b))

            turn_log.append({'turn': turn, 'lines': turn_lines})

            if hp_a <= 0 or hp_b <= 0:
                break

        # Победитель определяется по остатку HP (процент)
        hp_a = max(0, hp_a)
        hp_b = max(0, hp_b)

        pct_a = hp_a / max_hp_a if max_hp_a > 0 else 0
        pct_b = hp_b / max_hp_b if max_hp_b > 0 else 0

        if pct_a > pct_b:
            winner = 'a'; wins_a += 1
        elif pct_b > pct_a:
            winner = 'b'; wins_b += 1
        else:
            winner = 'draw'; draws += 1

        hp_a = round(hp_a)
        hp_b = round(hp_b)

        battle_log.append({
            'battle': battle_num,
            'winner': winner,
            'hp_a_left': hp_a,
            'hp_b_left': hp_b,
            'hp_a_pct': round(pct_a * 100, 1),
            'hp_b_pct': round(pct_b * 100, 1),
            'turns': len(turn_log),
            'turn_log': turn_log,
        })

    return {
        'wins_a': wins_a,
        'wins_b': wins_b,
        'draws': draws,
        'win_rate_a': round(wins_a / rounds * 100),
        'win_rate_b': round(wins_b / rounds * 100),
        'log': battle_log,
    }