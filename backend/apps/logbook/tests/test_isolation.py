from types import SimpleNamespace

import pytest

from apps.accounts.models import UserRole
from apps.accounts.tests.factories import (
    PlatformAdminFactory,
    RoleAssignmentFactory,
    UserFactory,
)
from apps.logbook.tests.factories import (
    PatientReferenceFactory,
    SurgicalProcedureFactory,
)
from apps.organizations.tests.factories import InstitutionFactory

pytestmark = pytest.mark.django_db

SECRET_MARKERS = ("Complication noted", "private case", "Alpha")


@pytest.fixture
def two():
    alpha = InstitutionFactory(name="Alpha Teaching Hospital")
    beta = InstitutionFactory(name="Beta Teaching Hospital")

    trainee_a = UserFactory(email="iso-trainee-a@example.test")
    RoleAssignmentFactory(user=trainee_a, role=UserRole.TRAINEE, institution=alpha)
    supervisor_a = UserFactory(email="iso-sup-a@example.test")
    RoleAssignmentFactory(user=supervisor_a, role=UserRole.SUPERVISOR, institution=alpha)

    trainee_b = UserFactory(email="iso-trainee-b@example.test")
    RoleAssignmentFactory(user=trainee_b, role=UserRole.TRAINEE, institution=beta)

    secret = SurgicalProcedureFactory(
        institution=alpha,
        author=trainee_a,
        procedure_name="private case",
        summary="Complication noted during closure.",
    )
    return SimpleNamespace(
        alpha=alpha,
        beta=beta,
        trainee_a=trainee_a,
        supervisor_a=supervisor_a,
        trainee_b=trainee_b,
        secret=secret,
    )


class TestInstitutionIsolation:
    def test_other_institution_user_gets_404_on_detail(self, client_factory, two):
        client = client_factory(two.trainee_b)
        response = client.get(f"/api/v1/procedures/{two.secret.pk}/")
        assert response.status_code == 404
        body = str(response.data)
        for marker in SECRET_MARKERS:
            assert marker not in body

    def test_other_institution_user_gets_404_on_lifecycle_actions(
        self, client_factory, two
    ):
        client = client_factory(two.trainee_b)
        base = f"/api/v1/procedures/{two.secret.pk}/"
        for path, method in (
            ("submit/", "post"),
            ("reviews/", "post"),
            ("archive/", "post"),
            ("participants/", "post"),
            ("attachments/", "post"),
        ):
            response = getattr(client, method)(f"{base}{path}", {}, format="json")
            assert response.status_code == 404, path

    def test_list_and_search_never_leak_other_institution(
        self, client_factory, two
    ):
        client = client_factory(two.trainee_b)
        listing = client.get("/api/v1/procedures/")
        assert listing.status_code == 200
        assert listing.data["results"] == []

        search = client.get("/api/v1/procedures/", {"search": "private"})
        assert search.data["results"] == []

        detail = client.get(f"/api/v1/procedures/{two.secret.pk}/")
        assert detail.status_code == 404

    def test_patch_other_institution_record_is_404_and_untouched(
        self, client_factory, two
    ):
        client = client_factory(two.trainee_b)
        response = client.patch(
            f"/api/v1/procedures/{two.secret.pk}/", {"summary": "tampered"}
        )
        assert response.status_code == 404
        two.secret.refresh_from_db()
        assert two.secret.summary == "Complication noted during closure."

    def test_supervisor_scoped_to_own_institution(self, client_factory, two):
        client = client_factory(two.supervisor_a)
        listing = client.get("/api/v1/procedures/")
        references = {row["reference"] for row in listing.data["results"]}
        assert two.secret.reference in references

        other_secret = SurgicalProcedureFactory(
            institution=two.beta, procedure_name="beta case"
        )
        listing = client.get("/api/v1/procedures/")
        references = {row["reference"] for row in listing.data["results"]}
        assert other_secret.reference not in references


class TestPlatformAdministrator:
    def test_platform_admin_has_no_clinical_access_by_default(
        self, client_factory, two
    ):
        admin = PlatformAdminFactory(email="iso-root@example.test")
        client = client_factory(admin)

        listing = client.get("/api/v1/procedures/")
        assert listing.status_code == 200
        assert listing.data["results"] == []

        detail = client.get(f"/api/v1/procedures/{two.secret.pk}/")
        assert detail.status_code == 404

        submit = client.post(f"/api/v1/procedures/{two.secret.pk}/submit/")
        assert submit.status_code == 404


class TestMarketplaceAccounts:
    def test_supplier_cannot_read_or_write_clinical_data(self, client_factory, two):
        supplier = UserFactory(email="iso-supplier@example.test")
        RoleAssignmentFactory(user=supplier, role=UserRole.SUPPLIER, institution=None)
        client = client_factory(supplier)

        assert client.get("/api/v1/procedures/").data["results"] == []
        assert (
            client.get(f"/api/v1/procedures/{two.secret.pk}/").status_code == 404
        )

        create = client.post(
            "/api/v1/procedures/",
            {
                "institution": two.alpha.pk,
                "procedure_date": "2026-09-21",
                "procedure_name": "Supplier case",
            },
        )
        assert create.status_code == 403

    def test_buyer_cannot_create_patient_reference(self, client_factory, two):
        buyer = UserFactory(email="iso-buyer@example.test")
        RoleAssignmentFactory(user=buyer, role=UserRole.BUYER, institution=None)
        client = client_factory(buyer)
        response = client.post(
            "/api/v1/patients/references/", {"institution": two.alpha.pk}
        )
        assert response.status_code == 403

    def test_supplier_not_addable_as_participant(self, client_factory, two):
        supplier = UserFactory(email="iso-sup-part@example.test")
        RoleAssignmentFactory(user=supplier, role=UserRole.SUPPLIER, institution=None)
        author = client_factory(two.trainee_a)
        response = author.post(
            f"/api/v1/procedures/{two.secret.pk}/participants/",
            {"user": supplier.pk, "role": "assistant"},
        )
        assert response.status_code == 400


class TestIndependentSurgeon:
    def test_can_create_in_any_institution_but_sees_only_own(
        self, client_factory, two
    ):
        surgeon = UserFactory(email="iso-independent@example.test")
        RoleAssignmentFactory(
            user=surgeon, role=UserRole.INDEPENDENT_SURGEON, institution=None
        )
        client = client_factory(surgeon)

        created = client.post(
            "/api/v1/procedures/",
            {
                "institution": two.alpha.pk,
                "procedure_date": "2026-09-22",
                "procedure_name": "Visiting surgeon case",
            },
        )
        assert created.status_code == 201, created.data

        listing = client.get("/api/v1/procedures/")
        references = {row["reference"] for row in listing.data["results"]}
        assert references == {created.data["reference"]}
        assert two.secret.reference not in references

        detail = client.get(f"/api/v1/procedures/{two.secret.pk}/")
        assert detail.status_code == 404

    def test_supervisor_sees_visiting_surgeon_record(self, client_factory, two):
        surgeon = UserFactory(email="iso-visiting@example.test")
        RoleAssignmentFactory(
            user=surgeon, role=UserRole.INDEPENDENT_SURGEON, institution=None
        )
        created = client_factory(surgeon).post(
            "/api/v1/procedures/",
            {
                "institution": two.alpha.pk,
                "procedure_date": "2026-09-23",
                "procedure_name": "Visiting case",
            },
        )
        assert created.status_code == 201

        listing = client_factory(two.supervisor_a).get("/api/v1/procedures/")
        references = {row["reference"] for row in listing.data["results"]}
        assert created.data["reference"] in references


class TestPatientReferenceIsolation:
    def test_reference_scoped_to_institution(self, client_factory, two):
        ref = PatientReferenceFactory(institution=two.alpha, label="OR-3 case")
        client = client_factory(two.trainee_b)
        listing = client.get("/api/v1/patients/references/")
        assert listing.status_code == 200
        assert listing.data["results"] == []
        assert client.get(
            f"/api/v1/patients/references/{ref.pk}/"
        ).status_code == 404

    def test_institution_member_sees_own_institution_references(
        self, client_factory, two
    ):
        ref = PatientReferenceFactory(institution=two.alpha, label="OR-3 case")
        client = client_factory(two.trainee_a)
        listing = client.get("/api/v1/patients/references/")
        codes = {row["code"] for row in listing.data["results"]}
        assert ref.code in codes

    def test_codes_are_random_and_unique_per_institution(self):
        ref_a = PatientReferenceFactory(institution=InstitutionFactory())
        ref_b = PatientReferenceFactory(institution=InstitutionFactory())
        assert ref_a.code.startswith("PR-")
        assert ref_a.code != ref_b.code
        # Codes never embed names or dates: fixed random format only.
        assert len(ref_a.code) == len("PR-") + 8
