import factory

from apps.accounts.tests.factories import UserFactory
from apps.logbook.models import (
    Attachment,
    PatientReference,
    ProcedureParticipant,
    SurgicalProcedure,
)
from apps.organizations.tests.factories import InstitutionFactory


class PatientReferenceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PatientReference

    institution = factory.SubFactory(InstitutionFactory)
    is_active = True


class SurgicalProcedureFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SurgicalProcedure

    institution = factory.SubFactory(InstitutionFactory)
    author = factory.SubFactory(UserFactory)
    procedure_date = factory.LazyFunction(
        lambda: __import__("datetime").date(2026, 9, 15)
    )
    procedure_name = factory.Sequence(lambda n: f"Procedure {n}")
    category = "elective"
    status = "draft"


class ProcedureParticipantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProcedureParticipant

    procedure = factory.SubFactory(SurgicalProcedureFactory)
    user = factory.SubFactory(UserFactory)
    role = "assistant"


class AttachmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Attachment

    procedure = factory.SubFactory(SurgicalProcedureFactory)
    original_name = "op-note.pdf"
    detected_kind = "application/pdf"
    size_bytes = 11
    sha256 = "0" * 64
    uploaded_by = factory.SubFactory(UserFactory)
