"""Create synthetic demonstration data (never real people or institutions)."""

import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.models import RoleAssignment, UserRole
from apps.organizations.models import Department, Institution, Specialty

DEMO_PASSWORD = "Demo!Passw0rd2026"

SPECIALTIES = [
    ("general-surgery", "General Surgery"),
    ("orthopedics", "Orthopedics"),
    ("neurosurgery", "Neurosurgery"),
    ("cardiothoracic", "Cardiothoracic Surgery"),
    ("urology", "Urology"),
    ("ent", "Ear, Nose and Throat"),
    ("ophthalmology", "Ophthalmology"),
    ("plastic-surgery", "Plastic and Reconstructive Surgery"),
]


class Command(BaseCommand):
    help = "Seed STAR with clearly synthetic demonstration institutions and accounts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--admin-email",
            default="platform-admin@demo.test",
            help="Email of the platform administrator to create.",
        )
        parser.add_argument(
            "--admin-password",
            default="",
            help="Password for the platform administrator (random when omitted).",
        )
        parser.add_argument(
            "--wipe",
            action="store_true",
            help="Only allow seeding when the database has no users yet.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.exists() and options["wipe"]:
            self.stderr.write("Refusing to seed: users already exist (--wipe set).")
            return

        admin_password = options["admin_password"] or secrets.token_urlsafe(16)
        admin, created = User.objects.get_or_create(
            email=options["admin_email"].lower(),
            defaults={
                "first_name": "Demo",
                "last_name": "Platform Admin",
                "is_platform_admin": True,
                "is_staff": True,
                "is_verified": True,
            },
        )
        if created:
            admin.set_password(admin_password)
            admin.save()
            self.stdout.write(
                self.style.WARNING(
                    f"Platform administrator created: {admin.email} / {admin_password}"
                )
            )
            self.stdout.write("Store this password safely — it is shown only once.")
        else:
            admin.is_platform_admin = True
            admin.save(update_fields=["is_platform_admin", "is_staff"])

        specialties = {}
        for code, name in SPECIALTIES:
            specialty, _ = Specialty.objects.get_or_create(
                code=code, defaults={"name": name}
            )
            specialties[code] = specialty

        demo_specs = [
            ("Demo General Hospital — North", "FR", "Lyon", ["general-surgery", "orthopedics"]),
            ("Demo University Medical Center", "FR", "Paris", ["neurosurgery", "cardiothoracic", "urology"]),
        ]

        for name, country, city, dept_names in demo_specs:
            institution, _ = Institution.objects.get_or_create(
                name=name,
                defaults={
                    "country": country,
                    "city": city,
                    "institution_type": "hospital",
                    "contact_email": "contact@demo.test",
                },
            )
            departments = []
            for dept_name in dept_names:
                department, _ = Department.objects.get_or_create(
                    institution=institution, name=dept_name.title()
                )
                departments.append(department)

            roles = [
                ("supervisor.demo@example.test", "Demo", "Supervisor", UserRole.SUPERVISOR, 0),
                ("examiner.demo@example.test", "Demo", "Examiner", UserRole.EXAMINER, 0),
                ("manager.demo@example.test", "Demo", "Manager", UserRole.DEPARTMENT_MANAGER, 0),
                ("inst-admin.demo@example.test", "Demo", "Inst Admin", UserRole.INSTITUTION_ADMIN, 0),
                ("trainee.demo@example.test", "Demo", "Trainee", UserRole.TRAINEE, 1),
                ("trainee2.demo@example.test", "Demo", "Trainee2", UserRole.TRAINEE, 1),
            ]
            for email, first, last, role, dept_idx in roles:
                user, user_created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "first_name": first,
                        "last_name": last,
                        "is_verified": True,
                    },
                )
                if user_created:
                    user.set_password(DEMO_PASSWORD)
                    user.save()
                RoleAssignment.objects.get_or_create(
                    user=user,
                    role=role,
                    institution=institution,
                    defaults={"department": departments[dept_idx] if departments else None},
                )

        for email, first, last, role in [
            ("surgeon.demo@example.test", "Demo", "Independent Surgeon", UserRole.INDEPENDENT_SURGEON),
            ("buyer.demo@example.test", "Demo", "Buyer", UserRole.BUYER),
            ("supplier.demo@example.test", "Demo", "Supplier", UserRole.SUPPLIER),
        ]:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"first_name": first, "last_name": last, "is_verified": True},
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            RoleAssignment.objects.get_or_create(user=user, role=role, institution=None)

        self.stdout.write(
            self.style.SUCCESS(
                f"Demonstration data ready. Shared demo password: {DEMO_PASSWORD}"
            )
        )
