from django.core.management.base import BaseCommand

from apps.marketplace import subscriptions


class Command(BaseCommand):
    help = (
        "Flip lapsed active seller subscriptions to 'expired' and cancel "
        "pending subscription checkouts whose payment window elapsed. "
        "Run it periodically alongside expire_marketplace_orders."
    )

    def handle(self, *args, **options):
        count = subscriptions.expire_stale_subscriptions()
        self.stdout.write(
            self.style.SUCCESS(f"Expired/cancelled {count} subscription(s).")
        )
