import factory

from apps.organizations.models import Department, Institution, Specialty


class InstitutionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Institution

    name = factory.Sequence(lambda n: f"General Hospital {n}")
    institution_type = "hospital"
    country = "FR"
    city = factory.Sequence(lambda n: f"City{n}")
    is_active = True


class DepartmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Department

    institution = factory.SubFactory(InstitutionFactory)
    name = factory.Sequence(lambda n: f"Department {n}")
    is_active = True


class SpecialtyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Specialty

    name = factory.Sequence(lambda n: f"Specialty {n}")
    code = factory.Sequence(lambda n: f"spec{n}")
    is_active = True
