from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.reports import services


class Command(BaseCommand):
    help = (
        "Delete report jobs and private artifacts whose retention window "
        "(REPORT_ARTIFACT_TTL_HOURS) has elapsed. Run it periodically; it exits "
        "non-zero when a file cannot be deleted or the expired backlog exceeds "
        "REPORT_RETENTION_BACKLOG_ALERT."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the expired backlog without deleting anything.",
        )
        parser.add_argument(
            "--max-backlog",
            type=int,
            default=None,
            help=(
                "Alert above this many expired jobs. Defaults to "
                "REPORT_RETENTION_BACKLOG_ALERT."
            ),
        )

    def handle(self, *args, **options):
        max_backlog = options["max_backlog"]
        if max_backlog is None:
            max_backlog = settings.REPORT_RETENTION_BACKLOG_ALERT

        result = services.purge_expired_report_jobs(dry_run=options["dry_run"])
        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Would purge {result.expired} expired report job(s)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Purged {result.purged} of {result.expired} expired "
                    f"report job(s); {result.failed} failed."
                )
            )

        problems = []
        if result.failed:
            problems.append(
                f"{result.failed} artifact(s) could not be deleted; their rows "
                "were kept for the next run"
            )
        if result.expired > max_backlog:
            problems.append(
                f"expired backlog {result.expired} exceeds threshold {max_backlog}"
            )
        if problems:
            raise CommandError(
                "Report retention needs attention: " + "; ".join(problems)
            )
