from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calculator', '0002_remove_grade_quality_add_dollslotstat'),
    ]

    operations = [
        migrations.AddField(
            model_name='doll',
            name='saved_state',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
