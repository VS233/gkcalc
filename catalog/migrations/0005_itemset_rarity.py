from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0004_effect_item_effect_setbonus_effect'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemset',
            name='rarity',
            field=models.CharField(
                choices=[
                    ('common', 'Common'), ('uncommon', 'Uncommon'),
                    ('rare', 'Rare'), ('epic', 'Epic'),
                    ('crafted', 'Crafted'), ('limited', 'Limited'),
                    ('legendary', 'Legendary'),
                ],
                default='common', max_length=16, verbose_name='Редкость'
            ),
        ),
    ]
