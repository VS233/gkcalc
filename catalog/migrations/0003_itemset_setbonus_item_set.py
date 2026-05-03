from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_item_rarity'),
    ]

    operations = [
        migrations.CreateModel(
            name='ItemSet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='Название сета')),
                ('description', models.TextField(blank=True, verbose_name='Описание')),
            ],
            options={'verbose_name': 'Сет', 'verbose_name_plural': 'Сеты', 'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='SetBonus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pieces_required', models.PositiveSmallIntegerField(verbose_name='Количество предметов')),
                ('value', models.FloatField(default=0, verbose_name='Значение бонуса')),
                ('item_set', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bonuses', to='catalog.itemset', verbose_name='Сет')),
                ('stat', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='catalog.stat', verbose_name='Стат')),
            ],
            options={'verbose_name': 'Бонус сета', 'verbose_name_plural': 'Бонусы сета', 'ordering': ['item_set', 'pieces_required']},
        ),
        migrations.AddField(
            model_name='item',
            name='item_set',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='items', to='catalog.itemset', verbose_name='Сет'),
        ),
    ]
