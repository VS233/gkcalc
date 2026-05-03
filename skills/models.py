from django.db import models


class SkillBranch(models.TextChoices):
    ATTACK  = 'attack',  'Атака'
    HEALTH  = 'health',  'Здоровье'
    DEFENSE = 'defense', 'Защита'


class SkillNode(models.Model):
    """Узел дерева навыков."""
    branch = models.CharField(max_length=16, choices=SkillBranch.choices, verbose_name='Ветка')
    order = models.PositiveSmallIntegerField(verbose_name='Порядок (строка сверху вниз)')
    name = models.CharField(max_length=64, verbose_name='Название навыка')
    description = models.TextField(blank=True, verbose_name='Описание')
    max_points = models.PositiveSmallIntegerField(default=1, verbose_name='Макс. очков (1-3)')
    icon = models.CharField(max_length=64, blank=True, verbose_name='CSS-класс иконки')

    class Meta:
        verbose_name = 'Узел навыка'
        verbose_name_plural = 'Узлы навыков'
        ordering = ['branch', 'order']
        unique_together = [('branch', 'order')]

    def __str__(self):
        return f'[{self.get_branch_display()}] {self.name} (ряд {self.order})'


class SkillEdge(models.Model):
    """Связь между узлами (вертикальная или диагональная)."""
    EDGE_VERTICAL  = 'vertical'
    EDGE_DIAGONAL  = 'diagonal'
    EDGE_CHOICES = [
        (EDGE_VERTICAL, 'Вертикальная'),
        (EDGE_DIAGONAL, 'Диагональная'),
    ]
    from_node = models.ForeignKey(SkillNode, on_delete=models.CASCADE, related_name='edges_from')
    to_node   = models.ForeignKey(SkillNode, on_delete=models.CASCADE, related_name='edges_to')
    edge_type = models.CharField(max_length=16, choices=EDGE_CHOICES, default=EDGE_VERTICAL)

    class Meta:
        verbose_name = 'Связь навыков'
        verbose_name_plural = 'Связи навыков'
        unique_together = [('from_node', 'to_node')]

    def __str__(self):
        return f'{self.from_node} → {self.to_node}'


class SkillBonus(models.Model):
    """Бонус к стату за вложенные очки в узел. Каждый уровень (кружок) — своё значение."""
    node = models.ForeignKey(SkillNode, on_delete=models.CASCADE, related_name='bonuses')
    stat = models.ForeignKey('catalog.Stat', on_delete=models.CASCADE)
    value_level_1 = models.FloatField(verbose_name='Значение за 1-й уровень')
    value_level_2 = models.FloatField(null=True, blank=True, verbose_name='Значение за 2-й уровень')
    value_level_3 = models.FloatField(null=True, blank=True, verbose_name='Значение за 3-й уровень')

    class Meta:
        verbose_name = 'Бонус навыка'
        verbose_name_plural = 'Бонусы навыков'
        unique_together = [('node', 'stat')]

    def get_value_for_points(self, points_invested):
        """Суммарный бонус за вложенные очки."""
        values = [self.value_level_1, self.value_level_2, self.value_level_3]
        total = 0.0
        for i in range(points_invested):
            v = values[i] if i < len(values) and values[i] is not None else 0
            total += v
        return total

    def __str__(self):
        return f'{self.node.name}: +{self.value_level_1} {self.stat.name_ru}/ур.1'