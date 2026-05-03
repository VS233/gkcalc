from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0003_itemset_setbonus_item_set'),
    ]

    operations = [
        migrations.CreateModel(
            name='Effect',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128, verbose_name='Название эффекта')),
                ('description', models.TextField(verbose_name='Описание эффекта')),
            ],
            options={'verbose_name': 'Эффект', 'verbose_name_plural': 'Эффекты', 'ordering': ['name']},
        ),
        migrations.AddField(
            model_name='setbonus',
            name='effect',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='catalog.effect', verbose_name='Эффект'),
        ),
        migrations.AddField(
            model_name='item',
            name='effect',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='catalog.effect', verbose_name='Эффект'),
        ),
    ]
