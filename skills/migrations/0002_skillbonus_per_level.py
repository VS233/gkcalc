from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('skills', '0001_initial'),
    ]

    operations = [
        # Переименовываем value_per_point -> value_level_1
        migrations.RenameField(
            model_name='skillbonus',
            old_name='value_per_point',
            new_name='value_level_1',
        ),
        # Добавляем value_level_2 и value_level_3 (nullable)
        migrations.AddField(
            model_name='skillbonus',
            name='value_level_2',
            field=models.FloatField(blank=True, null=True, verbose_name='Значение за 2-й уровень'),
        ),
        migrations.AddField(
            model_name='skillbonus',
            name='value_level_3',
            field=models.FloatField(blank=True, null=True, verbose_name='Значение за 3-й уровень'),
        ),
    ]
