import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('calculator', '0003_doll_saved_state'),
    ]

    operations = [
        migrations.CreateModel(
            name='DollSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('uuid', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ('state', models.JSONField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('doll', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='snapshots', to='calculator.doll')),
            ],
            options={'verbose_name': 'Снимок куклы', 'verbose_name_plural': 'Снимки кукол'},
        ),
    ]
