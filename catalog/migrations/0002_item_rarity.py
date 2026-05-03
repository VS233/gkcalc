from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
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
