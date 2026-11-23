from django.core.management.base import BaseCommand

from apps.reports import services


class Command(BaseCommand):
    help = (
        "Delete report jobs and private artifacts whose retention window "
        "(REPORT_ARTIFACT_TTL_HOURS) has elapsed. Run it periodically."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many expired jobs would be purged without deleting.",
        )

    def handle(self, *args, **options):
        count = services.purge_expired_report_jobs(dry_run=options["dry_run"])
        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(f"Would purge {count} expired report job(s).")
            )
            return
        self.stdout.write(
            self.style.SUCCESS(f"Purged {count} expired report job(s).")
        )
