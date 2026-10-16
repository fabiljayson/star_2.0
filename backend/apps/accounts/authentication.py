from rest_framework_simplejwt.authentication import JWTAuthentication as BaseJWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed


class JWTAuthentication(BaseJWTAuthentication):
    """JWT auth bound to the user's `auth_version`.

    Bumping `auth_version` (account disabled, "sign out everywhere") instantly
    invalidates every access *and* refresh token already issued.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        token_version = validated_token.payload.get("auth_version")
        if token_version != user.auth_version:
            raise AuthenticationFailed("Token has been revoked.", "token_revoked")
        return user
