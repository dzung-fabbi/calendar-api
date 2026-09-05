"""`python manage.py recompute_generations <clan_id>` or `--all`.

Recomputes `Person.generation` for an entire clan from scratch via
`services.tree.compute_generations` over `selectors.person.clan_edges`. Use
this after a bulk admin import or whenever `generation` is suspected to have
drifted -- the per-request hook in `views/person.py` only recomputes the
descendant subtree of the one person just edited, never the whole clan.
"""

from django.core.management.base import BaseCommand, CommandError

from giapha.models import Clan, Person
from giapha.selectors.person import clan_edges
from giapha.services.tree import compute_generations

BATCH_SIZE = 500


class Command(BaseCommand):
    help = 'Tính lại generation cho một dòng họ (<clan_id>) hoặc toàn bộ (--all).'

    def add_arguments(self, parser):
        parser.add_argument('clan_id', nargs='?', type=int, default=None)
        parser.add_argument(
            '--all', action='store_true', dest='all_clans',
            help='Tính lại cho mọi dòng họ chưa xoá.',
        )

    def handle(self, *args, **options):
        clan_id = options['clan_id']
        all_clans = options['all_clans']

        if all_clans and clan_id is not None:
            raise CommandError('Không dùng đồng thời <clan_id> và --all.')
        if not all_clans and clan_id is None:
            raise CommandError('Cần truyền <clan_id> hoặc --all.')

        clan_ids = (
            list(Clan.objects.filter(is_deleted=False).values_list('id', flat=True))
            if all_clans else [clan_id]
        )
        if not all_clans and not Clan.objects.filter(id=clan_id, is_deleted=False).exists():
            raise CommandError('Không tìm thấy dòng họ {}.'.format(clan_id))

        total_changed = 0
        for one_clan_id in clan_ids:
            total_changed += self._recompute_one_clan(one_clan_id)

        self.stdout.write(self.style.SUCCESS(
            'Đã tính lại generation cho {} bản ghi trong {} dòng họ.'.format(
                total_changed, len(clan_ids),
            )
        ))

    @staticmethod
    def _recompute_one_clan(clan_id):
        edges = clan_edges(clan_id)
        if not edges:
            return 0
        generations = compute_generations(edges)

        persons = list(
            Person.objects.filter(clan_id=clan_id, is_deleted=False).only('id', 'generation')
        )
        changed = []
        for person in persons:
            new_generation = generations.get(person.id)
            if person.generation != new_generation:
                person.generation = new_generation
                changed.append(person)

        if changed:
            Person.objects.bulk_update(changed, ['generation'], batch_size=BATCH_SIZE)
        return len(changed)
