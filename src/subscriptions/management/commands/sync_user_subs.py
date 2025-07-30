import helpers.billing
from typing import Any
from django.core.management.base import BaseCommand

from subscriptions import utils as subs_utils


class Command(BaseCommand):
    help = "Sync user subscriptions with Stripe or clear dangling subscriptions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--day-start",
            default=0,
            type=int,
            help="Start day offset for date range filtering (0 means not used)",
        )
        parser.add_argument(
            "--day-end",
            default=0,
            type=int,
            help="End day offset for date range filtering (0 means not used)",
        )
        parser.add_argument(
            "--days-left",
            default=0,
            type=int,
            help="Filter subscriptions ending in N days (0 means not used)",
        )
        parser.add_argument(
            "--days-ago",
            default=0,
            type=int,
            help="Filter subscriptions that ended N days ago (0 means not used)",
        )
        parser.add_argument(
            "--clear-dangling",
            action="store_true",
            default=False,
            help="Clear dangling subscriptions in Stripe that are not tracked locally",
        )

    def handle(self, *args: Any, **options: Any):
        # python manage.py sync_user_subs --clear-dangling
        # python manage.py sync_user_subs --days-left=7
        # python manage.py sync_user_subs --days-ago=3
        # python manage.py sync_user_subs --day-start=7 --day-end=30

        days_left = options.get("days_left", 0) or -1
        days_ago = options.get("days_ago", 0) or -1
        day_start = options.get("day_start", 0) or -1
        day_end = options.get("day_end", 0) or -1
        clear_dangling = options.get("clear_dangling", False)

        if clear_dangling:
            self.stdout.write("Clearing dangling active subscriptions in Stripe...")
            try:
                subs_utils.clear_dangling_subs()
                self.stdout.write(
                    self.style.SUCCESS("Successfully cleared dangling subscriptions")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error clearing dangling subscriptions: {str(e)}")
                )
                raise
        else:
            self.stdout.write("Syncing active user subscriptions...")
            # Show which filters are active
            filters_used = []
            if days_left > 0:
                filters_used.append(f"subscriptions ending in {days_left} days")
            if days_ago > 0:
                filters_used.append(f"subscriptions that ended {days_ago} days ago")
            if day_start > 0 and day_end > 0:
                filters_used.append(
                    f"subscriptions in range {day_start}-{day_end} days"
                )

            if filters_used:
                self.stdout.write(f"Filtering: {', '.join(filters_used)}")
            else:
                self.stdout.write("Syncing all active subscriptions")

            try:
                done = subs_utils.refresh_active_users_subscriptions(
                    active_only=True,
                    days_left=days_left,
                    days_ago=days_ago,
                    day_start=day_start,
                    day_end=day_end,
                    verbose=True,
                )
                if done:
                    self.stdout.write(
                        self.style.SUCCESS("Successfully synced all subscriptions")
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING("Some subscriptions could not be updated")
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error syncing subscriptions: {str(e)}")
                )
                raise
