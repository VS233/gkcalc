import uuid
from django.db import models
from django.conf import settings
from catalog.models import SlotType, Item, Stat


class Doll(models.Model):
    """Кукла персонажа — основная сущность калькулятора."""
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='dolls',
        verbose_name='Владелец',
    )
    name = models.CharField(max_length=64, default='Моя кукла', verbose_name='Название')
    character_level = models.PositiveSmallIntegerField(default=1, verbose_name='Уровень персонажа')
    stats_snapshot = models.JSONField(default=dict, blank=True)
    slot_order = models.PositiveSmallIntegerField(default=0, verbose_name='Номер слота')
    is_public = models.BooleanField(default=True, verbose_name='Публичная ссылка')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Кукла'
        verbose_name_plural = 'Куклы'
        ordering = ['slot_order']

    def __str__(self):
        return f'{self.name} (ур. {self.character_level})'

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('calculator:doll_public', kwargs={'uuid': self.uuid})


class DollSlot(models.Model):
    """Слот куклы — предмет с кастомными статами."""
    doll = models.ForeignKey(Doll, on_delete=models.CASCADE, related_name='slots')
    slot_type = models.CharField(max_length=20, choices=SlotType.choices, verbose_name='Тип слота')
    item = models.ForeignKey(
        Item, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Предмет',
    )

    class Meta:
        verbose_name = 'Слот куклы'
        verbose_name_plural = 'Слоты куклы'
        unique_together = [('doll', 'slot_type')]

    def __str__(self):
        return f'{self.doll.name} / {self.get_slot_type_display()}'

    def get_effective_stats(self):
        """
        Возвращает dict {stat_slug: значение}.
        Если есть кастомные статы — берём их,
        иначе базовые из ItemStat.
        """
        if not self.item:
            return {}
        custom = {cs.stat.slug: cs.value for cs in self.custom_stats.select_related('stat').all()}
        if custom:
            return custom
        # Базовые значения
        return {
            s.stat.slug: s.base_value
            for s in self.item.stats.select_related('stat').all()
        }

    def get_stats_with_diff(self):
        """
        Возвращает список dict для UI.
        Для обычных предметов — базовые статы с diff к кастомным.
        Для духа (нет ItemStat) — только кастомные статы.
        """
        if not self.item:
            return []
        base_map = {
            s.stat: s.base_value
            for s in self.item.stats.select_related('stat').all()
        }
        custom_map = {
            cs.stat: cs.value
            for cs in self.custom_stats.select_related('stat').all()
        }

        result = []
        # Все статы которые есть в базе или в кастомных
        all_stats = set(base_map.keys()) | set(custom_map.keys())
        for stat in sorted(all_stats, key=lambda s: s.order):
            base_val = base_map.get(stat)
            custom_val = custom_map.get(stat)
            display_val = custom_val if custom_val is not None else base_val
            if base_val is not None and base_val != 0 and custom_val is not None:
                diff_pct = round((custom_val - base_val) / base_val * 100, 1)
            else:
                diff_pct = None
            result.append({
                'stat': stat,
                'base_value': base_val,
                'custom_value': display_val,
                'diff_pct': diff_pct,
            })
        return result


class DollSlotStat(models.Model):
    """Кастомный стат предмета в слоте куклы."""
    doll_slot = models.ForeignKey(DollSlot, on_delete=models.CASCADE, related_name='custom_stats')
    stat = models.ForeignKey(Stat, on_delete=models.CASCADE)
    value = models.FloatField(verbose_name='Значение')

    class Meta:
        verbose_name = 'Кастомный стат слота'
        verbose_name_plural = 'Кастомные статы слотов'
        unique_together = [('doll_slot', 'stat')]

    def __str__(self):
        return f'{self.doll_slot} / {self.stat.name_ru} = {self.value}'


class DollSkill(models.Model):
    """Вложенные очки в узел навыка для конкретной куклы."""
    doll = models.ForeignKey(Doll, on_delete=models.CASCADE, related_name='skill_points')
    node = models.ForeignKey('skills.SkillNode', on_delete=models.CASCADE)
    points_invested = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Навык куклы'
        verbose_name_plural = 'Навыки куклы'
        unique_together = [('doll', 'node')]

    def __str__(self):
        return f'{self.doll.name} / {self.node}'