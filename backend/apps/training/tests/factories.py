from datetime import date

import factory

from apps.accounts.tests.factories import UserFactory
from apps.organizations.tests.factories import InstitutionFactory
from apps.training.models import (
    Assessment,
    Competency,
    CompetencyRubricVersion,
    TrainingPlacement,
)


class CompetencyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Competency

    institution = factory.SubFactory(InstitutionFactory)
    code = factory.Sequence(lambda n: f"COMP{n:03d}")
    title = factory.Sequence(lambda n: f"Competency {n}")


class CompetencyRubricVersionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CompetencyRubricVersion

    competency = factory.SubFactory(CompetencyFactory)
    version = 1
    levels = factory.LazyFunction(
        lambda: CompetencyRubricVersion.default_levels()
    )
    is_current = True


class TrainingPlacementFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TrainingPlacement

    institution = factory.SubFactory(InstitutionFactory)
    trainee = factory.SubFactory(UserFactory)
    start_date = date(2026, 10, 1)
    title = factory.Sequence(lambda n: f"Rotation {n}")
    status = "active"


class AssessmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Assessment

    placement = factory.SubFactory(TrainingPlacementFactory)
    competency = factory.SubFactory(CompetencyFactory)
    rubric_version = factory.SubFactory(CompetencyRubricVersionFactory)
    assessor = factory.SubFactory(UserFactory)
    scores = factory.LazyFunction(
        lambda: {"planning": "competent", "technique": "advanced_beginner"}
    )
    overall_level = "competent"
