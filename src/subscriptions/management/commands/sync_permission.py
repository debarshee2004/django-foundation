from typing import Any
from django.core.management.base import BaseCommand

from subscriptions import utils as subs_utils


class Command(BaseCommand):
    help = "Sync subscription permissions with Django groups"

    def handle(self, *args: Any, **options: Any):
        try:
            self.stdout.write("Starting permission synchronization...")
            subs_utils.sync_subs_group_permissions()
            self.stdout.write(
                self.style.SUCCESS(
                    "Successfully synced subscription permissions with groups"
                )
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error syncing permissions: {str(e)}"))
            raise
