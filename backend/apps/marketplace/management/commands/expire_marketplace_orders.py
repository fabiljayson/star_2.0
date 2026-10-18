from django.core.management.base import BaseCommand

from apps.marketplace import payments


class Command(BaseCommand):
    help = (
        "Cancel marketplace orders whose payment window (PAYMENT_PENDING_TTL_HOURS) "
        "elapsed, releasing their reserved stock. Run it periodically."
    )

    def handle(self, *args, **options):
        count = payments.expire_stale_orders()
        self.stdout.write(
            self.style.SUCCESS(f"Expired {count} stale pending order(s).")
        )
