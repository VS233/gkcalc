from django.core.management.base import BaseCommand
from skills.models import SkillNode, SkillEdge


class Command(BaseCommand):
    help = 'Создаёт вертикальные связи между узлами навыков (сверху вниз внутри каждой ветки)'

    def handle(self, *args, **kwargs):
        created = 0
        skipped = 0

        sections = SkillNode.objects.values_list('section', flat=True).distinct()
        branches = SkillNode.objects.values_list('branch', flat=True).distinct()

        for section in sections:
            for branch in branches:
                nodes = list(
                    SkillNode.objects.filter(section=section, branch=branch)
                    .order_by('order')
                )
                for i in range(len(nodes) - 1):
                    from_node = nodes[i]
                    to_node = nodes[i + 1]
                    edge, was_created = SkillEdge.objects.get_or_create(
                        from_node=from_node,
                        to_node=to_node,
                        defaults={'edge_type': SkillEdge.EDGE_VERTICAL}
                    )
                    if was_created:
                        created += 1
                        self.stdout.write(f'  + {from_node} → {to_node}')
                    else:
                        skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово. Создано: {created}, пропущено (уже было): {skipped}'
        ))