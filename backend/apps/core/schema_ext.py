"""drf-spectacular extensions for STAR's custom authentication classes.

Imported eagerly from `CoreConfig.ready` so the registry knows about them
before any schema is generated.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.plumbing import build_bearer_security_scheme_object


class JWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """Expose STAR's auth_version-bound JWT to the OpenAPI docs."""

    target_class = "apps.accounts.authentication.JWTAuthentication"
    name = "JWTAuth"
    match_subclasses = True
    priority = 1

    def get_security_definition(self, auto_schema):
        return build_bearer_security_scheme_object(
            header_name="HTTP_AUTHORIZATION",
            token_prefix="Bearer",
        )
