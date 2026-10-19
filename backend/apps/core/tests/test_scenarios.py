"""End-to-end scenario suite (Master Prompt §20, scenarios A–H).

Each scenario drives the real HTTP API end to end: every step is an
authenticated request (JWT login via `client_factory`), including the
sandbox payment webhook. ORM access is only used to build fixtures and
to assert state that the API deliberately hides.
"""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import UserRole
from apps.accounts.tests.factories import PlatformAdminFactory, UserFactory
from apps.core.models import AuditEvent
from apps.marketplace import payments as marketplace_payments
from apps.marketplace.models import (
    InventoryMovement,
    InventoryMovementReason,
    Order,
    Payment,
    PaymentEvent,
    PaymentEventType,
    PaymentStatus,
    ProductCategory,
    SupplierProfile,
)
from apps.marketplace.services import verify_supplier
from apps.organizations.tests.factories import DepartmentFactory, InstitutionFactory
from apps.training.tests.factories import (
    CompetencyFactory,
    CompetencyRubricVersionFactory,
    TrainingPlacementFactory,
)

pytestmark = pytest.mark.django_db

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


def wav_bytes() -> bytes:
    return b"RIFF" + (36).to_bytes(4, "little") + b"WAVEfmt " + b"\x00" * 24


def _error_code(response) -> str:
    return response.data.get("error", {}).get("code", "")


@pytest.fixture
def world():
    from apps.accounts.models import RoleAssignment
    institution_a = InstitutionFactory(name="Scenario Central Hospital")
    department_a = DepartmentFactory(institution=institution_a, name="General Surgery")
    institution_b = InstitutionFactory(name="Scenario Foreign Hospital")

    trainee_a = UserFactory(email="sc-trainee-a@example.test")
    RoleAssignment.objects.create(
        user=trainee_a,
        role=UserRole.TRAINEE,
        institution=institution_a,
        department=department_a,
    )
    supervisor_a = UserFactory(email="sc-supervisor-a@example.test")
    RoleAssignment.objects.create(
        user=supervisor_a, role=UserRole.SUPERVISOR, institution=institution_a
    )
    examiner_a = UserFactory(email="sc-examiner-a@example.test")
    RoleAssignment.objects.create(
        user=examiner_a, role=UserRole.EXAMINER, institution=institution_a
    )
    trainee_b = UserFactory(email="sc-trainee-b@example.test")
    RoleAssignment.objects.create(
        user=trainee_b, role=UserRole.TRAINEE, institution=institution_b
    )

    placement = TrainingPlacementFactory(
        institution=institution_a,
        department=department_a,
        trainee=trainee_a,
        supervisor=supervisor_a,
        title="Scenario rotation",
    )
    competency = CompetencyFactory(
        institution=institution_a, code="SC-COMP", title="Scenario competency"
    )
    rubric = CompetencyRubricVersionFactory(competency=competency)

    supplier_user = UserFactory(email="sc-supplier@example.test")
    RoleAssignment.objects.create(user=supplier_user, role=UserRole.SUPPLIER)
    platform_admin = PlatformAdminFactory(email="sc-platform@example.test")
    supplier = SupplierProfile.objects.create(
        user=supplier_user,
        company_name="Scenario Surgical Supply",
        contact_email=supplier_user.email,
    )
    verify_supplier(platform_admin, supplier, approve=True)
    category = ProductCategory.objects.create(name="Scalpels", slug="scalpels")
    product = supplier.products.create(
        category=category,
        name="Demo Scalpel",
        description="Fictional demo product",
        sku="SC-DEM-001",
        unit_price=Decimal("12000"),
        available_quantity=10,
        approval_status="approved",
        is_published=True,
    )

    buyer = UserFactory(email="sc-buyer@example.test")
    RoleAssignment.objects.create(user=buyer, role=UserRole.BUYER)

    return SimpleNamespace(
        institution_a=institution_a,
        department_a=department_a,
        institution_b=institution_b,
        trainee_a=trainee_a,
        supervisor_a=supervisor_a,
        examiner_a=examiner_a,
        trainee_b=trainee_b,
        placement=placement,
        competency=competency,
        rubric=rubric,
        buyer=buyer,
        product=product,
    )


def _procedure_payload(world, **overrides):
    payload = {
        "institution": str(world.institution_a.pk),
        "department": str(world.department_a.pk),
        "procedure_date": "2026-10-12",
        "procedure_name": "Inguinal hernia repair",
        "category": "elective",
        "indication": "Reducible right inguinal hernia",
        "summary": "Open Lichtenstein repair, mesh placed.",
    }
    payload.update(overrides)
    return payload


def _create_draft_procedure(api, world, **overrides) -> dict:
    response = api.post("/api/v1/procedures/", _procedure_payload(world, **overrides))
    assert response.status_code == 201, response.data
    return response.data


def _assessment_payload(world, **overrides):
    payload = {
        "placement": str(world.placement.pk),
        "competency": str(world.competency.pk),
        "scores": {
            "planning": "competent",
            "technique": "advanced_beginner",
            "safety": "competent",
            "professionalism": "proficient",
        },
        "overall_level": "competent",
        "feedback": "Solid fundamentals under supervision.",
    }
    payload.update(overrides)
    return payload


def _checkout_pending_order(api, world) -> tuple[dict, dict]:
    """Cart, checkout and open a payment attempt. Returns (order, payment)."""
    response = api.post(
        "/api/v1/marketplace/cart/items/",
        {"product": str(world.product.pk), "quantity": 2},
    )
    assert response.status_code == 201, response.data
    response = api.post("/api/v1/marketplace/checkout/", {})
    assert response.status_code == 201, response.data
    order = response.data[0]
    assert order["status"] == "pending_payment"
    pay = api.post(f"/api/v1/marketplace/orders/{order['id']}/pay/", {})
    assert pay.status_code == 201, pay.data
    payment = pay.data
    assert payment["status"] == PaymentStatus.PENDING
    return order, payment


def _webhook_body(payment: dict, order: dict, outcome: str) -> dict:
    payload = {
        "provider_reference": f"MOCK-{uuid4().hex}",
        "order_reference": order["reference"],
        "amount": payment["amount"],
        "currency": payment["currency"],
        "outcome": outcome,
        "timestamp": timezone.now().isoformat(),
    }
    return payload


def _post_webhook(api, payload) -> object:
    provider = APIClient()
    return provider.post(
        "/api/v1/marketplace/payments/webhook/",
        payload,
        format="json",
        HTTP_X_PAYMENT_SIGNATURE=marketplace_payments.sign_payload(payload),
    )


# ── Scenario A — Surgical logbook ──────────────────────────────────────
class TestScenarioASurgicalLogbook:
    def test_create_edit_attach_submit_review_status(self, client_factory, world):
        api = client_factory(world.trainee_a)
        procedure = _create_draft_procedure(api, world)
        assert procedure["status"] == "draft"

        edited = api.patch(
            f"/api/v1/procedures/{procedure['id']}/",
            {"summary": "Laparoscopic repair chosen after review."},
        )
        assert edited.status_code == 200, edited.data
        assert edited.data["status"] == "draft"

        upload = api.post(
            f"/api/v1/procedures/{procedure['id']}/attachments/",
            {"file": SimpleUploadedFile("op-note.pdf", PDF_BYTES, content_type="application/pdf")},
            format="multipart",
        )
        assert upload.status_code == 201, upload.data
        assert upload.data["detected_kind"] == "application/pdf"

        submitted = api.post(f"/api/v1/procedures/{procedure['id']}/submit/")
        assert submitted.status_code == 200, submitted.data
        assert submitted.data["status"] == "submitted"

        status_view = client_factory(world.supervisor_a).get(
            f"/api/v1/procedures/{procedure['id']}/"
        )
        assert status_view.status_code == 200, status_view.data
        author_view = api.get(f"/api/v1/procedures/{procedure['id']}/")
        assert author_view.data["status"] == "submitted"


# ── Scenario B — Trainee assessment ────────────────────────────────────
class TestScenarioBTraineeAssessment:
    def test_correction_requested_revised_then_approved(self, client_factory, world):
        supervisor = client_factory(world.supervisor_a)
        examiner = client_factory(world.examiner_a)
        assign = supervisor.post(
            f"/api/v1/training/placements/{world.placement.pk}/examiners/",
            {"examiner": world.examiner_a.pk},
        )
        assert assign.status_code == 201, assign.data

        created = supervisor.post("/api/v1/assessments/", _assessment_payload(world))
        assert created.status_code == 201, created.data
        assessment_id = created.data["id"]
        assert created.data["status"] == "draft"

        submitted = supervisor.post(f"/api/v1/assessments/{assessment_id}/submit/")
        assert submitted.status_code == 200, submitted.data
        assert submitted.data["status"] == "submitted"

        correction = examiner.post(
            f"/api/v1/assessments/{assessment_id}/decide/",
            {"decision": "needs_correction", "reason": "Justify the safety criterion."},
        )
        assert correction.status_code == 200, correction.data
        assert correction.data["status"] == "needs_correction"

        revised = supervisor.patch(
            f"/api/v1/assessments/{assessment_id}/",
            {"feedback": "Safety justification added after rework."},
        )
        assert revised.status_code == 200, revised.data
        resubmitted = supervisor.post(f"/api/v1/assessments/{assessment_id}/submit/")
        assert resubmitted.status_code == 200, resubmitted.data
        assert resubmitted.data["status"] == "submitted"

        approved = examiner.post(
            f"/api/v1/assessments/{assessment_id}/decide/", {"decision": "approved"}
        )
        assert approved.status_code == 200, approved.data
        assert approved.data["status"] == "approved"

        audit_actions = list(
            AuditEvent.objects.filter(object_pk=str(assessment_id))
            .order_by("created_at")
            .values_list("action", flat=True)
        )
        lifecycle = [
            action
            for action in audit_actions
            if action
            in {
                AuditEvent.Action.ASSESSMENT_CREATED,
                AuditEvent.Action.ASSESSMENT_SUBMITTED,
                AuditEvent.Action.ASSESSMENT_DECIDED,
                AuditEvent.Action.ASSESSMENT_UPDATED,
            }
        ]
        assert lifecycle == [
            AuditEvent.Action.ASSESSMENT_CREATED,
            AuditEvent.Action.ASSESSMENT_SUBMITTED,
            AuditEvent.Action.ASSESSMENT_DECIDED,
            AuditEvent.Action.ASSESSMENT_UPDATED,
            AuditEvent.Action.ASSESSMENT_SUBMITTED,
            AuditEvent.Action.ASSESSMENT_DECIDED,
        ]


# ── Scenario C — Unauthorized access ───────────────────────────────────
class TestScenarioCUnauthorizedAccess:
    def test_outsider_gets_opaque_404s(self, client_factory, world):
        author = client_factory(world.trainee_a)
        procedure = _create_draft_procedure(author, world)

        outsider = client_factory(world.trainee_b)
        procedure_view = outsider.get(f"/api/v1/procedures/{procedure['id']}/")
        assert procedure_view.status_code == 404, procedure_view.data
        assert _error_code(procedure_view) == "not_found"
        assert procedure["procedure_name"] not in str(procedure_view.content)

        supervisor = client_factory(world.supervisor_a)
        created = supervisor.post("/api/v1/assessments/", _assessment_payload(world))
        assert created.status_code == 201, created.data

        assessment_view = outsider.get(f"/api/v1/assessments/{created.data['id']}/")
        assert assessment_view.status_code == 404, assessment_view.data
        assert _error_code(assessment_view) == "not_found"


# ── Scenario D — Marketplace order ─────────────────────────────────────
class TestScenarioDMarketplaceOrder:
    def test_checkout_pending_then_confirmed_by_verified_webhook(self, client_factory, world):
        api = client_factory(world.buyer)
        order, payment = _checkout_pending_order(api, world)

        payload = _webhook_body(payment, order, "succeeded")
        response = _post_webhook(api, payload)
        assert response.status_code == 200, response.data
        assert response.data["status"] == PaymentStatus.SUCCEEDED

        order_view = api.get(f"/api/v1/marketplace/orders/{order['id']}/")
        assert order_view.status_code == 200, order_view.data
        assert order_view.data["status"] == "paid"
        assert order_view.data["payments"][0]["status"] == PaymentStatus.SUCCEEDED

        world.product.refresh_from_db()
        assert world.product.available_quantity == 8
        assert world.product.reserved_quantity == 0
        movement = InventoryMovement.objects.get(
            order_id=order["id"], reason=InventoryMovementReason.SOLD
        )
        assert movement.reason == InventoryMovementReason.SOLD
        assert movement.delta == -2


# ── Scenario E — Duplicate payment notification ────────────────────────
class TestScenarioEDuplicatePaymentNotification:
    def test_same_webhook_twice_has_single_financial_effect(self, client_factory, world):
        api = client_factory(world.buyer)
        order, payment = _checkout_pending_order(api, world)
        payload = _webhook_body(payment, order, "succeeded")

        first = _post_webhook(api, payload)
        assert first.status_code == 200, first.data
        duplicate = _post_webhook(api, payload)
        assert duplicate.status_code == 200, duplicate.data
        assert duplicate.data["status"] == PaymentStatus.SUCCEEDED

        assert PaymentEvent.objects.filter(
            payment_id=payment["id"], event_type=PaymentEventType.DUPLICATE_IGNORED
        ).count() == 1
        assert (
            InventoryMovement.objects.filter(
                order_id=order["id"], reason=InventoryMovementReason.SOLD
            ).count()
            == 1
        )
        assert AuditEvent.objects.filter(
            action=AuditEvent.Action.PAYMENT_SUCCEEDED, object_pk=payment["id"]
        ).count() == 1

        order_view = api.get(f"/api/v1/marketplace/orders/{order['id']}/")
        assert order_view.data["status"] == "paid"


# ── Scenario F — Failed payment ────────────────────────────────────────
class TestScenarioFFailedPayment:
    def test_failed_webhook_then_ttl_expiry_releases_stock(self, client_factory, world, capsys):
        api = client_factory(world.buyer)
        order, payment = _checkout_pending_order(api, world)
        payload = _webhook_body(payment, order, "failed")
        response = _post_webhook(api, payload)
        assert response.status_code == 200, response.data
        assert response.data["status"] == PaymentStatus.FAILED

        payment_row = Payment.objects.get(pk=payment["id"])
        assert payment_row.status == PaymentStatus.FAILED
        assert payment_row.failure_reason
        order_row = Order.objects.get(pk=order["id"])
        assert order_row.status == "pending_payment"
        world.product.refresh_from_db()
        assert world.product.reserved_quantity == 2, "stock stays reserved while retryable"

        order_row.placed_at = timezone.now() - timedelta(hours=25)
        order_row.save(update_fields=["placed_at", "updated_at"])
        call_command("expire_marketplace_orders")
        assert "Expired 1" in capsys.readouterr().out

        order_row.refresh_from_db()
        assert order_row.status == "cancelled"
        assert order_row.cancel_reason == "Payment window expired"
        world.product.refresh_from_db()
        assert world.product.available_quantity == 10
        assert world.product.reserved_quantity == 0
        assert (
            InventoryMovement.objects.filter(
                order_id=order["id"], reason=InventoryMovementReason.RELEASED
            ).exists()
        )


# ── Scenario G — Reporting ─────────────────────────────────────────────
class TestScenarioGReporting:
    def test_authorized_report_succeeds_out_of_scope_denied(self, client_factory, world):
        author = client_factory(world.trainee_a)
        _create_draft_procedure(author, world)

        supervisor = client_factory(world.supervisor_a)
        created = supervisor.post(
            "/api/v1/reports/",
            {
                "institution": str(world.institution_a.pk),
                "report_type": "activity_by_date",
                "format": "csv",
            },
        )
        assert created.status_code == 201, created.data
        assert created.data["status"] == "succeeded"
        assert created.data["row_count"] >= 1

        download = supervisor.get(f"/api/v1/reports/{created.data['id']}/download/")
        assert download.status_code == 200, download.data
        assert download["Content-Type"].startswith("text/csv")

        trainee = client_factory(world.trainee_a)
        denied = trainee.post(
            "/api/v1/reports/",
            {
                "institution": str(world.institution_a.pk),
                "report_type": "activity_by_date",
                "format": "csv",
            },
        )
        assert denied.status_code == 403, denied.data
        assert _error_code(denied) == "permission_denied"

        foreign = supervisor.post(
            "/api/v1/reports/",
            {
                "institution": str(world.institution_b.pk),
                "report_type": "activity_by_date",
                "format": "csv",
            },
        )
        assert foreign.status_code == 403, foreign.data


# ── Scenario H — Voice transcription failure ───────────────────────────
class TestScenarioHTranscriptionFailure:
    def test_failure_keeps_draft_then_manual_continue(self, client_factory, world):
        api = client_factory(world.trainee_a)
        original_summary = "Original dictated note."
        procedure = _create_draft_procedure(api, world, summary=original_summary)

        with override_settings(TRANSCRIPTION_MOCK_FAILURE=True):
            failed = api.post(
                f"/api/v1/procedures/{procedure['id']}/transcribe/",
                {
                    "audio": SimpleUploadedFile(
                        "dictation.wav", wav_bytes(), content_type="audio/wav"
                    ),
                    "language": "en",
                },
                format="multipart",
            )
        assert failed.status_code == 503, failed.data
        assert _error_code(failed) == "transcription_unavailable"

        procedure_row_view = api.get(f"/api/v1/procedures/{procedure['id']}/")
        assert procedure_row_view.data["status"] == "draft"
        assert procedure_row_view.data["summary"] == original_summary

        edited = api.patch(
            f"/api/v1/procedures/{procedure['id']}/",
            {"summary": "Manually corrected note after transcription failure."},
        )
        assert edited.status_code == 200, edited.data
        submitted = api.post(f"/api/v1/procedures/{procedure['id']}/submit/")
        assert submitted.status_code == 200, submitted.data
        assert submitted.data["status"] == "submitted"
