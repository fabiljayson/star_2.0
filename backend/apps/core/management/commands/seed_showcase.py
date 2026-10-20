"""Seed STAR with a large synthetic showcase dataset (never real people).

Every row is fictional: institutions are prefixed "Showcase", accounts use
`@*.showcase.test` addresses and every clinical note is placeholder text.
Lifecycle transitions go through the real domain services, so audit events,
notifications, review histories, payments and disputes look authentic.
"""

import random
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import RoleAssignment, UserRole
from apps.logbook import services as logbook_services
from apps.logbook.models import PatientReference, ProcedureParticipant, SurgicalProcedure
from apps.marketplace import payments as marketplace_payments
from apps.marketplace import services as marketplace_services
from apps.marketplace.models import (
    Product,
    ProductCategory,
    SellerSubscription,
)
from apps.notifications.models import Notification
from apps.organizations.models import Department, Institution, Specialty
from apps.reports import services as reports_services
from apps.training import services as training_services
from apps.training.models import Competency, TrainingPlacement

SHOWCASE_PASSWORD = "Demo!Passw0rd2026"
RNG = random.Random(20261018)

FIRST_NAMES = [
    "Amara", "Kwame", "Fatou", "Ibrahim", "Nadia", "Tomas", "Grace", "Ousmane",
    "Leila", "Marcus", "Aisha", "Daniel", "Mariam", "Yusuf", "Chidi", "Zara",
    "Paul", "Esther", "Hassan", "Clara", "Emeka", "Sofia", "Jonas", "Rania",
]
LAST_NAMES = [
    "Okafor", "Diallo", "Mensah", "Traore", "Benali", "Novak", "Adeyemi", "Sow",
    "Haddad", "Lindqvist", "Osei", "Karanja", "Fofana", "Balogun", "Nwosu", "Dube",
    "Marek", "Boateng", "Salem", "Owusu", "Eze", "Camara", "Fischer", "Njeri",
]

INSTITUTION_SPECS = [
    {
        "name": "Showcase University Hospital — Abidjan",
        "short": "ABJ",
        "country": "CI",
        "city": "Abidjan",
        "departments": [
            ("General Surgery", "GS", "general-surgery"),
            ("Orthopedics", "ORT", "orthopedics"),
            ("Urology", "URO", "urology"),
            ("Neurosurgery", "NEURO", "neurosurgery"),
        ],
    },
    {
        "name": "Showcase Central Surgical Institute — Dakar",
        "short": "DKR",
        "country": "SN",
        "city": "Dakar",
        "departments": [
            ("General Surgery", "GS", "general-surgery"),
            ("Cardiothoracic Surgery", "CTS", "cardiothoracic"),
            ("Ear, Nose and Throat", "ENT", "ent"),
        ],
    },
    {
        "name": "Showcase Children's Surgical Center — Lomé",
        "short": "LME",
        "country": "TG",
        "city": "Lomé",
        "departments": [
            ("General Surgery", "GS", "general-surgery"),
            ("Pediatric Surgery", "PEDS", "plastic-surgery"),
            ("Ophthalmology", "OPH", "ophthalmology"),
        ],
    },
    {
        "name": "Showcase Trauma Institute — Bamako",
        "short": "BKO",
        "country": "ML",
        "city": "Bamako",
        "departments": [
            ("Orthopedics", "ORT", "orthopedics"),
            ("General Surgery", "GS", "general-surgery"),
            ("Plastic and Reconstructive Surgery", "PRS", "plastic-surgery"),
        ],
    },
]

EXTRA_SPECIALTIES = [
    ("vascular-surgery", "Vascular Surgery"),
    ("pediatric-surgery", "Pediatric Surgery"),
    ("minimally-invasive", "Minimally Invasive Surgery"),
]

PROCEDURE_NAMES_BY_SPECIALTY = {
    "general-surgery": [
        "Laparoscopic cholecystectomy", "Inguinal hernia repair (open)",
        "Appendectomy", "Incisional hernia repair", "Laparoscopic appendectomy",
        "Small bowel resection", "Hemorrhoidectomy", "Excision of pilonidal cyst",
    ],
    "orthopedics": [
        "Open reduction and internal fixation of distal radius fracture",
        "Total hip arthroplasty", "Arthroscopic meniscectomy",
        "Intramedullary nailing of tibial fracture", "K-wire fixation of metacarpal fracture",
    ],
    "urology": [
        "Transurethral resection of the prostate", "Laparoscopic pyeloplasty",
        "Ureteroscopic lithotripsy", "Circumcision (adult)", "Scrotal exploration",
    ],
    "neurosurgery": [
        "Chronic subdural hematoma evacuation", "Lumbar discectomy",
        "Burr hole drainage", "Ventriculoperitoneal shunt revision",
    ],
    "cardiothoracic": [
        "Median sternotomy and pericardial window", "Video-assisted thoracoscopic surgery",
        "Chest tube insertion (trauma)", "Rib fixation",
    ],
    "ent": [
        "Tonsillectomy", "Septoplasty", "FESS (functional endoscopic sinus surgery)",
        "Tympanoplasty",
    ],
    "ophthalmology": [
        "Phacoemulsification with IOL implantation", "Pterygium excision",
        "Intravitreal injection",
    ],
    "plastic-surgery": [
        "Split-thickness skin graft", "Z-plasty scar revision",
        "Primary closure of complex laceration", "Digital replantation planning",
    ],
}
FALLBACK_PROCEDURES = ["Diagnostic laparoscopy", "Wound exploration and debridement"]

INDICATIONS = [
    "Symptomatic cholelithiasis with recurrent biliary colic.",
    "Traumatic fracture with loss of reduction after closed management.",
    "Recurrent urinary retention unresponsive to medical therapy.",
    "Progressive neurological deficit with corresponding imaging findings.",
    "Elective correction of congenital deformity affecting daily function.",
    "Acute inflammatory process confirmed on laboratory and imaging work-up.",
]
SUMMARIES = [
    "Patient taken to theatre after checklist verification; procedure completed uneventfully via standard approach.",
    "Procedure performed under general anaesthesia with the patient in the standard position; findings as expected.",
    "Minimally invasive approach used; conversion to open was not required and estimated blood loss was minimal.",
    "Case completed with meticulous haemostasis; specimen sent to histology as routine.",
]
COMPLICATIONS = [
    "",
    "",
    "",
    "Minor intra-operative bleeding controlled with cautery; no post-operative transfusion required.",
    "Small seroma noted at follow-up, managed conservatively.",
]
POSTOP = [
    "Uneventful recovery; discharged on post-operative day 2 with analgesia and wound care instructions.",
    "Recovery as expected; sutures removed at day 10, follow-up scheduled.",
    "Stable post-operative course; physiotherapy involved early and mobilisation progressed well.",
    "Observed overnight for monitoring; discharged the following morning in good condition.",
]

SUPPLIER_SPECS = [
    ("Showcase MedTrade SARL", "CI", "Abidjan", True),
    ("Showcase Surgical Imports Ltd", "SN", "Dakar", True),
    ("Showcase Ortho Supply", "TG", "Lomé", True),
    ("Showcase Sterile Solutions", "ML", "Bamako", True),
    ("Showcase Unverified Trading", "CI", "Yamoussoukro", False),
]

PRODUCT_SPECS = [
    ("Disposable surgical gloves (box of 100)", "Consumables"),
    ("Absorbable sutures 2-0", "Sutures"),
    ("Non-absorbable sutures 0 nylon", "Sutures"),
    ("Scalpel blades No. 10 (box of 100)", "Blades"),
    ("Metzenbaum scissors", "Instrument sets"),
    ("Mayo scissors (straight)", "Instrument sets"),
    ("Curved artery forceps", "Forceps"),
    ("Needle holder, 14 cm", "Instrument sets"),
    ("Retractor set, abdominal", "Retractors"),
    ("Chest drain, 28 Fr", "Consumables"),
    ("Surgical masks (box of 50)", "Consumables"),
    ("Sterile drape packs", "Consumables"),
    ("Bone plate, titanium, 8-hole", "Implants"),
    ("K-wires, 2.0 mm (pack of 10)", "Implants"),
    ("Patient warming blanket", "Monitors"),
    ("Pulse oximeter, handheld", "Monitors"),
]

SHIPPING_TEMPLATE = {
    "name": "Showcase Procurement Office",
    "address": "Boulevard du Centre, Lot 12, Abidjan",
    "phone": "+225 07 00 00 00",
}


class Command(BaseCommand):
    help = "Seed a large synthetic showcase dataset (institutions, users, records, marketplace)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Top up data even if a showcase seed appears to exist.",
        )

    def handle(self, *args, **options):
        started = timezone.now()
        self.force = options["force"]
        User = get_user_model()
        already = User.objects.filter(email__endswith="@showcase.test").exists()
        if already and not self.force:
            self.stdout.write(
                "Showcase accounts already exist. Re-run with --force to top up."
            )
            return

        self.admin = User.objects.filter(is_platform_admin=True).first()
        if self.admin is None:
            self.stdout.write(self.style.ERROR("No platform administrator found."))
            return

        self._seed_specialties()
        self.institutions = self._seed_institutions()
        self._seed_users()
        self._seed_logbook()
        self._seed_training()
        self._seed_marketplace()
        self._seed_reports()
        self._polish_timestamps()

        elapsed = (timezone.now() - started).total_seconds()
        self.stdout.write(
            self.style.SUCCESS(
                f"Showcase dataset ready in {elapsed:.1f}s. "
                f"Shared password: {SHOWCASE_PASSWORD}"
            )
        )

    # ── Organizations & accounts ────────────────────────────────────────
    def _seed_specialties(self):
        for code, name in EXTRA_SPECIALTIES:
            Specialty.objects.get_or_create(code=code, defaults={"name": name})

    def _seed_institutions(self):
        institutions = []
        for spec in INSTITUTION_SPECS:
            institution, _ = Institution.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "country": spec["country"],
                    "city": spec["city"],
                    "institution_type": "hospital",
                    "contact_email": f"contact@{spec['short'].lower()}.showcase.test",
                },
            )
            spec["object"] = institution
            spec["departments"] = [
                {
                    "name": dname,
                    "code": dcode,
                    "specialty": Specialty.objects.filter(code=sc).first(),
                    "object": Department.objects.get_or_create(
                        institution=institution, name=dname, defaults={"code": dcode}
                    )[0],
                }
                for dname, dcode, sc in spec["departments"]
            ]
            institutions.append(spec)
        return institutions

    def _next_name(self, used: set[str]) -> tuple[str, str, str]:
        while True:
            first = RNG.choice(FIRST_NAMES)
            last = RNG.choice(LAST_NAMES)
            email = f"{first}.{last}{len(used) + 1}@showcase.test".lower()
            if email not in used:
                used.add(email)
                return email, first, last

    def _make_user(self, used: set[str], *, first=None, last=None, email=None):
        User = get_user_model()
        if email is None:
            email, first, last = self._next_name(used)
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first or "",
                "last_name": last or "",
                "is_verified": True,
            },
        )
        if created:
            user.set_password(SHOWCASE_PASSWORD)
            user.save()
        return user

    def _grant(self, user, role, institution=None, department=None):
        RoleAssignment.objects.get_or_create(
            user=user,
            role=role,
            institution=institution,
            defaults={"department": department, "granted_by": self.admin},
        )

    def _seed_users(self):
        self.people = {}
        used: set[str] = set()
        per_inst = {"trainees": 10, "supervisors": 3, "examiners": 2, "managers": 2}

        for spec in self.institutions:
            inst = spec["object"]
            people = {
                "trainees": [],
                "supervisors": [],
                "examiners": [],
                "managers": [],
                "admin": None,
            }
            people["admin"] = self._make_user(used)
            self._grant(people["admin"], UserRole.INSTITUTION_ADMIN, inst)
            for _ in range(per_inst["managers"]):
                u = self._make_user(used)
                self._grant(u, UserRole.DEPARTMENT_MANAGER, inst, RNG.choice(spec["departments"])["object"])
                people["managers"].append(u)
            for _ in range(per_inst["supervisors"]):
                u = self._make_user(used)
                self._grant(u, UserRole.SUPERVISOR, inst, RNG.choice(spec["departments"])["object"])
                people["supervisors"].append(u)
            for _ in range(per_inst["examiners"]):
                u = self._make_user(used)
                self._grant(u, UserRole.EXAMINER, inst)
                people["examiners"].append(u)
            for _ in range(per_inst["trainees"]):
                u = self._make_user(used)
                self._grant(u, UserRole.TRAINEE, inst, RNG.choice(spec["departments"])["object"])
                people["trainees"].append(u)
            spec["people"] = people
            self.people[inst.pk] = people

        self.surgeons = [self._make_user(used) for _ in range(4)]
        for u in self.surgeons:
            self._grant(u, UserRole.INDEPENDENT_SURGEON)

        self.buyers = [self._make_user(used) for _ in range(8)]
        for u in self.buyers:
            self._grant(u, UserRole.BUYER)

        self.suppliers = []
        for company, country, city, verified in SUPPLIER_SPECS:
            u = self._make_user(
                used,
                email=f"sales.{company.split()[1].lower()}{len(self.suppliers) + 1}@supplier.showcase.test".lower(),
                first="Sales",
                last=company.split()[1],
            )
            self._grant(u, UserRole.SUPPLIER)
            self.suppliers.append({"user": u, "company": company, "country": country,
                                   "city": city, "verified": verified, "profile": None,
                                   "short": company.split()[1].lower()[:6]})

    # ── Surgical logbook ────────────────────────────────────────────────
    def _reviewer_for(self, spec, author):
        candidates = spec["people"]["supervisors"] + spec["people"]["examiners"] + [spec["people"]["admin"]]
        candidates = [c for c in candidates if c.pk != author.pk]
        return RNG.choice(candidates) if candidates else None

    def _seed_logbook(self):
        existing = SurgicalProcedure.objects.filter(
            institution__name__startswith="Showcase"
        ).count()
        if existing >= 120 and not self.force:
            return
        target_per_institution = 40
        status_mix = (
            ["draft"] * 6 + ["submitted"] * 6 + ["under_review"] * 4 +
            ["approved"] * 12 + ["returned"] * 4 + ["archived"] * 8
        )
        for spec in self.institutions:
            inst = spec["object"]
            have = SurgicalProcedure.objects.filter(institution=inst).count()
            if have >= target_per_institution:
                continue
            authors = spec["people"]["trainees"] + spec["people"]["supervisors"]
            for _ in range(target_per_institution - have):
                author = RNG.choice(authors)
                dept = RNG.choice(spec["departments"])
                specialty = dept["specialty"]
                names = PROCEDURE_NAMES_BY_SPECIALTY.get(
                    getattr(specialty, "code", ""), FALLBACK_PROCEDURES
                )
                proc_date = timezone.localdate() - timedelta(days=RNG.randint(5, 330))
                ref = PatientReference.objects.create(
                    institution=inst,
                    created_by=author,
                    label=f"SHOWCASE OR-{RNG.randint(1, 9)} (fictional)",
                )
                procedure = SurgicalProcedure.objects.create(
                    institution=inst,
                    department=dept["object"],
                    specialty=specialty,
                    patient_reference=ref,
                    author=author,
                    procedure_date=proc_date,
                    category=RNG.choice(["elective", "emergency", "trauma", "diagnostic"]),
                    procedure_name=RNG.choice(names),
                    indication=RNG.choice(INDICATIONS),
                    summary=RNG.choice(SUMMARIES),
                    complications=RNG.choice(COMPLICATIONS),
                    postoperative=RNG.choice(POSTOP),
                    training_objectives="Synthetic showcase objective (fictional case).",
                )
                others = [
                    u for u in (
                        spec["people"]["trainees"] + spec["people"]["supervisors"]
                    )
                    if u.pk != author.pk
                ]
                for other in RNG.sample(others, k=min(len(others), RNG.choice([1, 1, 2]))):
                    ProcedureParticipant.objects.create(
                        procedure=procedure,
                        user=other,
                        role=RNG.choice(["primary_operator", "assistant", "observer"]),
                    )

                target = RNG.choice(status_mix)
                reviewer = self._reviewer_for(spec, author)
                if target == "draft":
                    continue
                logbook_services.submit_procedure(procedure, actor=author)
                if target == "submitted":
                    continue
                if reviewer is None:
                    continue
                if target == "under_review":
                    logbook_services.review_procedure(
                        procedure, actor=reviewer, decision="start_review"
                    )
                elif target == "approved":
                    logbook_services.review_procedure(
                        procedure, actor=reviewer, decision="approve"
                    )
                elif target == "returned":
                    logbook_services.review_procedure(
                        procedure,
                        actor=reviewer,
                        decision="request_correction",
                        reason="Showcase review: clarify the post-operative plan (synthetic).",
                    )
                elif target == "archived":
                    logbook_services.review_procedure(
                        procedure, actor=reviewer, decision="approve"
                    )
                    logbook_services.archive_procedure(procedure, actor=reviewer)

    # ── Training ────────────────────────────────────────────────────────
    def _seed_training(self):
        for spec in self.institutions:
            inst = spec["object"]
            people = spec["people"]
            if not people["trainees"]:
                continue
            competencies = []
            for idx, dept in enumerate(spec["departments"], start=1):
                competency, _ = Competency.objects.get_or_create(
                    institution=inst,
                    code=f"{spec['short']}-{dept['code']}-01",
                    defaults={
                        "title": f"Showcase competency — {dept['name']} fundamentals",
                        "description": "Synthetic showcase competency (fictional).",
                        "specialty": dept["specialty"],
                        "order": idx,
                    },
                )
                if not competency.rubric_versions.exists():
                    training_services.create_rubric_version(
                        competency, actor=RNG.choice(people["managers"] + [people["admin"]])
                    )
                competencies.append(competency)

            for idx, trainee in enumerate(people["trainees"]):
                supervisor = people["supervisors"][idx % len(people["supervisors"])]
                dept = spec["departments"][idx % len(spec["departments"])]
                past_title = f"Showcase prior rotation — {dept['name']}"
                if not TrainingPlacement.objects.filter(trainee=trainee, title=past_title).exists():
                    past = training_services.create_placement(
                        supervisor,
                        validated_data={
                            "title": past_title,
                            "institution": inst,
                            "department": dept["object"],
                            "trainee": trainee,
                            "supervisor": supervisor,
                            "start_date": date(2025, 3, 1),
                            "end_date": date(2025, 10, 31),
                            "objectives": "Synthetic prior placement (fictional).",
                        },
                        expected_competency_ids=[c.pk for c in competencies[:2]],
                    )
                    training_services.complete_placement(past, actor=supervisor)

                title = f"Showcase rotation — {dept['name']} ({spec['short']})"
                if TrainingPlacement.objects.filter(trainee=trainee, title=title).exists():
                    continue
                placement = training_services.create_placement(
                    supervisor,
                    validated_data={
                        "title": title,
                        "institution": inst,
                        "department": dept["object"],
                        "trainee": trainee,
                        "supervisor": supervisor,
                        "start_date": date(2026, 9, 1),
                        "end_date": date(2027, 2, 28),
                        "objectives": "Synthetic showcase placement objectives (fictional).",
                    },
                    expected_competency_ids=[c.pk for c in competencies],
                )
                examiners = RNG.sample(
                    people["examiners"], k=min(len(people["examiners"]), 2)
                )
                for examiner in examiners:
                    training_services.assign_examiner(
                        placement, actor=supervisor, examiner=examiner
                    )
                self._seed_assessments(placement, competencies, examiners, supervisor)

    def _seed_assessments(self, placement, competencies, examiners, supervisor):
        from apps.training.models import AssessmentStatus

        if not examiners:
            return
        levels = ["novice", "advanced_beginner", "competent", "proficient"]
        criteria = ["planning", "technique", "safety", "professionalism"]
        outcomes = ["approved"] * 5 + ["submitted", "draft", "needs_correction", "rejected"]
        for competency in RNG.sample(competencies, k=min(3, len(competencies))):
            outcome = RNG.choice(outcomes)
            assessor = RNG.choice(examiners)
            scores = {
                criterion: RNG.choice(levels)
                for criterion in RNG.sample(criteria, k=RNG.randint(2, 4))
            }
            assessment = training_services.create_assessment(
                assessor,
                placement=placement,
                competency=competency,
                validated_data={
                    "scores": scores,
                    "overall_level": RNG.choice(levels),
                    "feedback": "Synthetic showcase feedback (fictional placement).",
                },
            )
            if outcome == "draft":
                continue
            training_services.submit_assessment(assessment, actor=assessor)
            if outcome == "submitted":
                continue
            if outcome == "approved":
                training_services.decide_assessment(
                    assessment,
                    actor=supervisor,
                    decision=AssessmentStatus.APPROVED,
                    feedback="Solid progress demonstrated (synthetic showcase).",
                )
            elif outcome == "needs_correction":
                training_services.decide_assessment(
                    assessment,
                    actor=supervisor,
                    decision=AssessmentStatus.NEEDS_CORRECTION,
                    reason="Expand on the safety commentary (synthetic showcase).",
                )
            elif outcome == "rejected":
                training_services.decide_assessment(
                    assessment,
                    actor=supervisor,
                    decision=AssessmentStatus.REJECTED,
                    reason="Evidence does not yet meet the rubric (synthetic showcase).",
                )

    # ── Marketplace ─────────────────────────────────────────────────────
    def _seed_marketplace(self):
        categories = {}
        for name in sorted({p[1] for p in PRODUCT_SPECS}):
            slug = name.lower().replace(" ", "-")
            categories[name], _ = ProductCategory.objects.get_or_create(
                name=name, defaults={"slug": slug}
            )

        admin = self.admin
        for supplier in self.suppliers:
            SellerSubscription.objects.get_or_create(
                user=supplier["user"],
                status="active",
                defaults={
                    "plan": "semiannual",
                    "amount": Decimal("10000"),
                    "currency": "XOF",
                    "starts_at": timezone.now() - timedelta(days=30),
                    "expires_at": timezone.now() + timedelta(days=150),
                },
            )
            profile = marketplace_services.register_or_update_profile(
                supplier["user"],
                data={
                    "company_name": supplier["company"],
                    "contact_email": supplier["user"].email,
                    "contact_phone": "+225 07 11 22 33",
                    "address": f"Zone industrielle, {supplier['city']}",
                    "commercial_notes": "Synthetic showcase supplier (fictional).",
                },
            )
            supplier["profile"] = profile
            if supplier["verified"] and profile.verification_status != "verified":
                marketplace_services.verify_supplier(admin, profile, approve=True)

        verified_products = []
        for supplier in self.suppliers:
            profile = supplier["profile"]
            for idx, (pname, category_name) in enumerate(PRODUCT_SPECS, start=1):
                sku = f"{supplier['short'].upper()}-{idx:03d}"
                product, created = Product.objects.get_or_create(
                    supplier=profile,
                    sku=sku,
                    defaults={
                        "category": categories[category_name],
                        "name": pname,
                        "description": "Synthetic showcase catalogue item (fictional).",
                        "unit_price": Decimal(RNG.randint(2, 260) * 1000),
                        "available_quantity": 0,
                        "is_published": True,
                    },
                )
                if created and supplier["verified"]:
                    marketplace_services.decide_product(admin, product, approve=True)
                    marketplace_services.restock(
                        product,
                        RNG.randint(25, 200),
                        actor=profile.user,
                    )
                    verified_products.append(product)
                elif product.approval_status == "approved":
                    verified_products.append(product)

        if not verified_products:
            return
        scenarios = [
            "pending", "paid", "delivered", "refunded", "refund_rejected",
            "dispute_open", "dispute_buyer", "dispute_supplier", "cancelled", "failed_payment",
        ]
        for buyer in self.buyers:
            for round_no in range(3):
                scenario = scenarios[(buyer.email.__hash__() + round_no) % len(scenarios)]
                supplier = RNG.choice([s for s in self.suppliers if s["verified"]])
                products = [
                    p for p in verified_products if p.supplier_id == supplier["profile"].pk
                ]
                if not products:
                    continue
                for product in RNG.sample(products, k=min(len(products), RNG.randint(1, 3))):
                    quantity = RNG.randint(1, 4)
                    try:
                        marketplace_services.add_to_cart(
                            buyer, product=product, quantity=quantity
                        )
                    except Exception:
                        continue
                cart_items = marketplace_services.get_or_create_cart(buyer).items.all()
                if not cart_items.exists():
                    continue
                try:
                    orders = marketplace_services.checkout(
                        buyer, shipping=dict(SHIPPING_TEMPLATE)
                    )
                except Exception:
                    continue
                if not orders:
                    continue
                order = orders[0]
                supplier_user = order.supplier.user
                try:
                    self._advance_order(order, scenario, buyer, supplier_user)
                except Exception as exc:
                    self.stdout.write(
                        f"NOTE: order {order.reference} ({scenario}) stopped at {exc}"
                    )

    def _advance_order(self, order, scenario, buyer, supplier_user):
        if scenario == "pending":
            return
        if scenario == "cancelled":
            marketplace_services.cancel_order(
                order, actor=buyer, reason="Showcase cancellation (synthetic)."
            )
            return
        if scenario == "failed_payment":
            payment, _ = marketplace_payments.initiate_payment(
                order, buyer=buyer, idempotency_key=f"seed-{uuid.uuid4().hex}"
            )
            marketplace_payments.simulate_payment(payment, outcome="failed")
            return

        payment, _ = marketplace_payments.initiate_payment(
            order, buyer=buyer, idempotency_key=f"seed-{uuid.uuid4().hex}"
        )
        marketplace_payments.simulate_payment(payment, outcome="succeeded")
        order.refresh_from_db()
        if scenario == "paid":
            return
        marketplace_services.ship_order(
            order,
            actor=supplier_user,
            tracking_number=f"SHOW-{RNG.randint(100000, 999999)}",
        )
        if scenario == "shipped":
            return
        marketplace_services.deliver_order(order, actor=supplier_user)
        if scenario == "delivered":
            return
        if scenario in {"refunded", "refund_rejected"}:
            refund = marketplace_services.request_refund(
                order, buyer=buyer, reason="Showcase refund request (synthetic)."
            )
            marketplace_services.decide_refund(
                refund,
                actor=supplier_user,
                approved=scenario == "refunded",
                decision_reason="Showcase decision (synthetic).",
            )
            return
        # dispute scenarios
        dispute = marketplace_services.open_dispute(
            order,
            user=buyer,
            description="Showcase dispute: item arrived damaged (synthetic).",
        )
        marketplace_services.add_dispute_evidence(
            dispute, user=buyer, body="Photos of packaging on arrival (synthetic note)."
        )
        marketplace_services.add_dispute_evidence(
            dispute, user=supplier_user, body="Dispatch checklist reference (synthetic note)."
        )
        if scenario == "dispute_open":
            return
        marketplace_services.resolve_dispute(
            dispute,
            actor=self.admin,
            resolution="buyer_favored" if scenario == "dispute_buyer" else "supplier_favored",
            note="Showcase resolution after evidence review (synthetic).",
        )

    # ── Reports ─────────────────────────────────────────────────────────
    def _seed_reports(self):
        date_from = (timezone.localdate() - timedelta(days=180)).isoformat()
        date_to = timezone.localdate().isoformat()
        for spec in self.institutions:
            inst = spec["object"]
            people = spec["people"]
            try:
                reports_services.request_report(
                    people["admin"],
                    institution=inst,
                    report_type="institution_summary",
                    report_format="csv",
                    parameters={"date_from": date_from, "date_to": date_to},
                )
                trainee = people["trainees"][0]
                reports_services.request_report(
                    trainee,
                    institution=inst,
                    report_type="individual_logbook",
                    report_format="csv",
                    parameters={"date_from": date_from, "date_to": date_to},
                )
            except Exception as exc:
                self.stdout.write(f"NOTE: report for {inst.name} skipped: {exc}")
        try:
            reports_services.request_report(
                self.admin,
                institution=None,
                report_type="marketplace_summary",
                report_format="csv",
                parameters={"date_from": date_from, "date_to": date_to},
            )
        except Exception as exc:
            self.stdout.write(f"NOTE: marketplace report skipped: {exc}")

    # ── Realistic timestamps ────────────────────────────────────────────
    def _polish_timestamps(self):
        now = timezone.now()
        for procedure in SurgicalProcedure.objects.filter(
            institution__name__startswith="Showcase"
        ):
            base = datetime.combine(
                procedure.procedure_date + timedelta(days=RNG.randint(0, 3)),
                time(RNG.randint(7, 19), RNG.randint(0, 59)),
                tzinfo=timezone.get_current_timezone(),
            )
            SurgicalProcedure.objects.filter(pk=procedure.pk).update(
                created_at=base, updated_at=base
            )
            fields = {}
            if procedure.submitted_at:
                fields["submitted_at"] = base + timedelta(hours=RNG.randint(2, 20))
            if procedure.approved_at:
                fields["approved_at"] = fields.get(
                    "submitted_at", base
                ) + timedelta(days=RNG.randint(1, 10))
            if procedure.archived_at:
                fields["archived_at"] = fields.get(
                    "approved_at", base
                ) + timedelta(days=RNG.randint(20, 90))
            if fields:
                SurgicalProcedure.objects.filter(pk=procedure.pk).update(**fields)

        showcase_pks = list(
            SurgicalProcedure.objects.filter(
                institution__name__startswith="Showcase"
            ).values_list("pk", flat=True)
        )
        for model in (ProcedureParticipant, PatientReference):
            if model is ProcedureParticipant:
                qs = model.objects.filter(procedure_id__in=showcase_pks)
            else:
                qs = model.objects.filter(
                    institution__name__startswith="Showcase"
                )
            for obj in qs[:500]:
                stamp = now - timedelta(days=RNG.randint(1, 300))
                qs.model.objects.filter(pk=obj.pk).update(created_at=stamp)

        notifications = Notification.objects.filter(
            recipient__email__endswith="@showcase.test"
        )
        for idx, pk in enumerate(
            notifications.values_list("pk", flat=True)[:2000]
        ):
            stamp = now - timedelta(hours=RNG.randint(1, 24 * 90))
            read = (idx % 5) != 0
            Notification.objects.filter(pk=pk).update(
                created_at=stamp,
                updated_at=stamp,
                is_read=read,
                read_at=stamp + timedelta(hours=1) if read else None,
            )
