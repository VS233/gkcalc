from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('calculator', '0001_initial'),
        ('catalog', '0004_effect_item_effect_setbonus_effect'),
    ]

    operations = [
        migrations.RemoveField(model_name='dollslot', name='grade'),
        migrations.RemoveField(model_name='dollslot', name='quality'),
        migrations.CreateModel(
            name='DollSlotStat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.FloatField(verbose_name='Значение')),
                ('doll_slot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='custom_stats', to='calculator.dollslot')),
                ('stat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='catalog.stat')),
            ],
            options={'verbose_name': 'Кастомный стат слота', 'verbose_name_plural': 'Кастомные статы слотов', 'unique_together': {('doll_slot', 'stat')}},
        ),
    ]
