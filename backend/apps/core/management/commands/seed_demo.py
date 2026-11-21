"""Create synthetic demonstration data (never real people or institutions)."""

import secrets
from datetime import date

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

        self._seed_logbook()
        self._seed_training()
        self._seed_marketplace()

        self.stdout.write(
            self.style.SUCCESS(
                f"Demonstration data ready. Shared demo password: {DEMO_PASSWORD}"
            )
        )

    def _seed_marketplace(self):
        """Synthetic marketplace: verified supplier, one approved product (fictional)."""
        from decimal import Decimal

        from apps.marketplace.models import (
            Product,
            ProductCategory,
            SellerSubscription,
            SupplierProfile,
        )

        User = get_user_model()
        from datetime import timedelta

        from django.utils import timezone

        supplier = User.objects.get(email="supplier.demo@example.test")
        seller_sub, _ = SellerSubscription.objects.get_or_create(
            user=supplier,
            status="active",
            defaults={
                "plan": "monthly",
                "amount": Decimal("5000"),
                "currency": "XOF",
                "starts_at": timezone.now() - timedelta(days=1),
                "expires_at": timezone.now() + timedelta(days=29),
            },
        )

        if Product.objects.exists():
            return

        admin = User.objects.filter(is_platform_admin=True).first()
        profile, created = SupplierProfile.objects.get_or_create(
            user=supplier,
            defaults={
                "company_name": "Demo Surgical Supplies",
                "contact_email": "supplier.demo@example.test",
                "verification_status": "verified",
                "verified_by": admin,
            },
        )
        if created and admin is not None:
            profile.verified_at = timezone.now()
            profile.save()

        category, _ = ProductCategory.objects.get_or_create(
            name="Forceps", slug="forceps"
        )
        product = Product.objects.create(
            supplier=profile,
            category=category,
            name="Demo Disposable Forceps",
            description="Synthetic marketplace demo product (fictional).",
            sku="DEM-FP-001",
            image="marketplace/products/artery-forceps.jpg",
            image_credit="Splarka · public domain",
            unit_price=Decimal("15000"),
            available_quantity=10,
            approval_status="approved",
            approved_by=admin,
            is_published=True,
        )
        if admin is not None:
            from django.utils import timezone

            product.approved_at = timezone.now()
            product.save()

    def _seed_training(self):
        """Synthetic placements, competencies and assessments (fictional)."""
        from apps.training import services as training_services
        from apps.training.models import (
            Competency,
            ExaminerAssignment,
            TrainingPlacement,
        )

        User = get_user_model()
        if TrainingPlacement.objects.exists():
            return

        institution = Institution.objects.filter(
            name="Demo General Hospital — North"
        ).first()
        if institution is None:
            return
        trainee = User.objects.get(email="trainee.demo@example.test")
        supervisor = User.objects.get(email="supervisor.demo@example.test")
        examiner = User.objects.get(email="examiner.demo@example.test")
        manager = User.objects.get(email="manager.demo@example.test")
        department = Department.objects.filter(institution=institution).first()

        placement = TrainingPlacement.objects.create(
            institution=institution,
            department=department,
            trainee=trainee,
            supervisor=supervisor,
            start_date=date(2026, 9, 1),
            end_date=date(2027, 2, 28),
            title="Synthetic demo — general surgery rotation",
            objectives="Synthetic training objectives for demonstration only.",
            created_by=supervisor,
        )

        competencies = [
            Competency.objects.create(
                institution=institution,
                code="DEMO-CHOLE",
                title="Synthetic demo — cholecystectomy fundamentals",
                description="Fictional competency used by the seed.",
            ),
            Competency.objects.create(
                institution=institution,
                code="DEMO-HERNIA",
                title="Synthetic demo — hernia repair fundamentals",
                description="Fictional competency used by the seed.",
            ),
        ]
        for competency in competencies:
            training_services.create_rubric_version(competency, actor=manager)
        placement.expected_competencies.set(competencies)

        ExaminerAssignment.objects.create(
            placement=placement, examiner=examiner, assigned_by=supervisor
        )

        first = training_services.create_assessment(
            examiner,
            placement=placement,
            competency=competencies[0],
            validated_data={
                "scores": {
                    "planning": "competent",
                    "technique": "advanced_beginner",
                    "safety": "competent",
                    "professionalism": "proficient",
                },
                "overall_level": "competent",
                "feedback": "Synthetic demo feedback (fictional).",
            },
        )
        training_services.submit_assessment(first, actor=examiner)
        training_services.decide_assessment(
            first, actor=supervisor, decision="approved",
            feedback="Synthetic demo approval (fictional).",
        )

        training_services.create_assessment(
            examiner,
            placement=placement,
            competency=competencies[1],
            validated_data={
                "scores": {"planning": "advanced_beginner"},
                "overall_level": "advanced_beginner",
                "feedback": "Synthetic demo draft feedback (fictional).",
            },
        )

    def _seed_logbook(self):
        """Synthetic surgical records — clearly fictional, no real patients."""
        from apps.logbook import services as logbook_services
        from apps.logbook.models import (
            PatientReference,
            ProcedureParticipant,
            SurgicalProcedure,
        )

        User = get_user_model()
        if SurgicalProcedure.objects.exists():
            return

        institution = Institution.objects.filter(
            name="Demo General Hospital — North"
        ).first()
        if institution is None:
            return
        trainee = User.objects.get(email="trainee.demo@example.test")
        trainee2 = User.objects.get(email="trainee2.demo@example.test")
        supervisor = User.objects.get(email="supervisor.demo@example.test")
        department = Department.objects.filter(institution=institution).first()

        def _reference(label):
            return PatientReference.objects.create(
                institution=institution, created_by=trainee, label=label
            )

        def _procedure(name, date, *, ref, status="draft"):
            procedure = SurgicalProcedure.objects.create(
                institution=institution,
                department=department,
                patient_reference=ref,
                author=trainee,
                procedure_date=date,
                procedure_name=name,
                category="elective",
                indication="DEMOGRAPHIC-FREE synthetic indication text.",
                summary="Synthetic operative summary used for demonstration only.",
                postoperative="Synthetic recovery notes for demo purposes.",
            )
            ProcedureParticipant.objects.create(
                procedure=procedure, user=trainee2, role="assistant"
            )
            if status == "submitted":
                logbook_services.submit_procedure(procedure, actor=trainee)
            elif status == "approved":
                logbook_services.submit_procedure(procedure, actor=trainee)
                logbook_services.review_procedure(
                    procedure, actor=supervisor, decision="approve"
                )
            return procedure

        _procedure(
            "Synthetic demo — laparoscopic cholecystectomy",
            date(2026, 10, 6),
            ref=_reference("DEMO OR-1 (fictional)"),
            status="approved",
        )
        _procedure(
            "Synthetic demo — inguinal hernia repair",
            date(2026, 10, 12),
            ref=_reference("DEMO OR-2 (fictional)"),
            status="submitted",
        )
        _procedure(
            "Synthetic demo — appendectomy (draft)",
            date(2026, 10, 15),
            ref=_reference("DEMO OR-3 (fictional)"),
        )
