from django.db import models


class SlotType(models.TextChoices):
    MAIN_WEAPON   = 'main_weapon',   'Основное оружие'
    OFF_WEAPON    = 'off_weapon',    'Дополнительное оружие'
    HELMET        = 'helmet',        'Шлем'
    ARMOR         = 'armor',         'Броня'
    AMPLIFIER     = 'amplifier',     'Усилитель'
    ACCESSORY     = 'accessory',     'Аксессуар'
    GUARDIAN      = 'guardian',      'Дух-хранитель'


class Stat(models.Model):
    """Справочник всех возможных статов."""
    slug = models.SlugField(unique=True, verbose_name='Идентификатор')
    name_ru = models.CharField(max_length=64, verbose_name='Название')
    CATEGORY_POWER = 'power'
    CATEGORY_RESIST = 'resistance'
    CATEGORY_CHOICES = [
        (CATEGORY_POWER, 'Мощь'),
        (CATEGORY_RESIST, 'Сопротивление'),
    ]
    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES, default=CATEGORY_POWER)
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок отображения')
    is_percent = models.BooleanField(default=False, verbose_name='В процентах')

    class Meta:
        verbose_name = 'Стат'
        verbose_name_plural = 'Статы'
        ordering = ['order']

    def __str__(self):
        return self.name_ru


class Rarity(models.TextChoices):
    COMMON    = 'common',    'Common'
    UNCOMMON  = 'uncommon',  'Uncommon'
    RARE      = 'rare',      'Rare'
    EPIC      = 'epic',      'Epic'
    CRAFTED   = 'crafted',   'Crafted'
    LIMITED   = 'limited',   'Limited'
    LEGENDARY = 'legendary', 'Legendary'


class Effect(models.Model):
    """Эффект — текстовое описание особого свойства."""
    name = models.CharField(max_length=128, verbose_name='Название эффекта')
    description = models.TextField(verbose_name='Описание эффекта')

    class Meta:
        verbose_name = 'Эффект'
        verbose_name_plural = 'Эффекты'
        ordering = ['name']

    def __str__(self):
        return self.name


class ItemSet(models.Model):
    """Сет предметов."""
    name = models.CharField(max_length=128, verbose_name='Название сета')
    description = models.TextField(blank=True, verbose_name='Описание')
    rarity = models.CharField(
        max_length=16, choices=Rarity.choices,
        default=Rarity.COMMON, verbose_name='Редкость'
    )

    class Meta:
        verbose_name = 'Сет'
        verbose_name_plural = 'Сеты'
        ordering = ['name']

    def __str__(self):
        return self.name


class SetBonus(models.Model):
    """Бонус сета при надевании N предметов."""
    item_set = models.ForeignKey(ItemSet, on_delete=models.CASCADE, related_name='bonuses')
    pieces_required = models.PositiveSmallIntegerField(verbose_name='Количество предметов')
    stat = models.ForeignKey(
        Stat, on_delete=models.CASCADE, null=True, blank=True,
        verbose_name='Стат'
    )
    value = models.FloatField(default=0, verbose_name='Значение бонуса')
    effect = models.ForeignKey(
        Effect, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Эффект'
    )

    class Meta:
        verbose_name = 'Бонус сета'
        verbose_name_plural = 'Бонусы сета'
        ordering = ['item_set', 'pieces_required']

    def __str__(self):
        stat_name = self.stat.name_ru if self.stat else '—'
        return f'{self.item_set.name} ({self.pieces_required} пред.): +{self.value} {stat_name}'


class Item(models.Model):
    """Предмет в базе — заполняется администратором."""
    name = models.CharField(max_length=128, verbose_name='Название')
    slot_type = models.CharField(max_length=20, choices=SlotType.choices, verbose_name='Тип слота')
    rarity = models.CharField(
        max_length=16, choices=Rarity.choices,
        default=Rarity.COMMON, verbose_name='Редкость'
    )
    item_set = models.ForeignKey(
        ItemSet, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='items',
        verbose_name='Сет'
    )
    # Эффект — только для духа-хранителя, но технически доступно любому предмету
    effect = models.ForeignKey(
        Effect, on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Эффект'
    )
    description = models.TextField(blank=True, verbose_name='Описание')
    image = models.ImageField(upload_to='items/', blank=True, null=True, verbose_name='Иконка')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        verbose_name = 'Предмет'
        verbose_name_plural = 'Предметы'
        ordering = ['slot_type', 'name']

    def __str__(self):
        return f'{self.get_slot_type_display()} — {self.name}'


class ItemStat(models.Model):
    """Базовый стат предмета (без учёта качества и грейда)."""
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='stats')
    stat = models.ForeignKey(Stat, on_delete=models.CASCADE)
    base_value = models.FloatField(verbose_name='Базовое значение')

    class Meta:
        verbose_name = 'Стат предмета'
        verbose_name_plural = 'Статы предмета'
        unique_together = [('item', 'stat')]

    def __str__(self):
        return f'{self.item.name}: {self.stat.name_ru} = {self.base_value}'