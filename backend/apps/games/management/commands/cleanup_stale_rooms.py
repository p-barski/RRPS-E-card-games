from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.games.models import Room


class Command(BaseCommand):
    help = (
        "Deletes stale rooms: WAITING rooms nobody ever joined "
        "(STALE_WAITING_ROOM_MINUTES), plus any room past a hard age limit "
        "(STALE_ROOM_MAX_AGE_HOURS) regardless of status, to catch games "
        "abandoned mid-play. Intended to run periodically (e.g. via cron)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true", help="Report what would be deleted without deleting it."
        )

    def handle(self, *args, **options):
        now = timezone.now()
        waiting_cutoff = now - timedelta(minutes=settings.STALE_WAITING_ROOM_MINUTES)
        max_age_cutoff = now - timedelta(hours=settings.STALE_ROOM_MAX_AGE_HOURS)

        stale_ids = set(
            Room.objects.filter(status=Room.Status.WAITING, created_at__lt=waiting_cutoff).values_list(
                "id", flat=True
            )
        )
        stale_ids.update(Room.objects.filter(created_at__lt=max_age_cutoff).values_list("id", flat=True))

        if options["dry_run"]:
            self.stdout.write(f"Would delete {len(stale_ids)} stale room(s).")
            return

        Room.objects.filter(id__in=stale_ids).delete()
        self.stdout.write(f"Deleted {len(stale_ids)} stale room(s).")
