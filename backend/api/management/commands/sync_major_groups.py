from django.core.management.base import BaseCommand

from api.services.major_sync import sync_major_groups


class Command(BaseCommand):
    help = 'Apply MAJOR_ALIASES / MAJOR_ABSORPTIONS and the sub-major rule onto the Major table'

    def handle(self, *args, **options):
        aliases, grouped = sync_major_groups()
        self.stdout.write(self.style.SUCCESS(f'Majors synced: {aliases} aliases, {grouped} grouped under a parent.'))
