import factory

from apps.accounts.models import RoleAssignment, User, UserRole

DEFAULT_TEST_PASSWORD = "Str0ng!Passw0rd"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.test")
    first_name = "Demo"
    last_name = "User"
    is_active = True
    is_verified = True

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or DEFAULT_TEST_PASSWORD)
        if create:
            self.save(update_fields=["password"])


class PlatformAdminFactory(UserFactory):
    is_platform_admin = True
    email = factory.Sequence(lambda n: f"platform{n}@example.test")


class RoleAssignmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RoleAssignment

    user = factory.SubFactory(UserFactory)
    is_active = True


def make_institution_admin(user, institution, department=None) -> RoleAssignment:
    return RoleAssignmentFactory(
        user=user, role=UserRole.INSTITUTION_ADMIN, institution=institution
    )
