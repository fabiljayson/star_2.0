from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.settings import api_settings

User = get_user_model()


class StarTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Refresh/access tokens carrying the `auth_version` revocation claim."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["auth_version"] = user.auth_version
        return token


class StarTokenRefreshSerializer(TokenRefreshSerializer):
    """Refresh flow that refuses tokens issued before a revocation."""

    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])

        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM, None)
        if user_id:
            user = User.objects.filter(
                **{api_settings.USER_ID_FIELD: user_id}
            ).first()
            if user is None or not api_settings.USER_AUTHENTICATION_RULE(user):
                raise AuthenticationFailed(
                    self.error_messages["no_active_account"], "no_active_account"
                )
            if refresh.payload.get("auth_version") != user.auth_version:
                raise AuthenticationFailed("Token has been revoked.", "token_revoked")

        data = {"access": str(refresh.access_token)}

        if api_settings.ROTATE_REFRESH_TOKENS:
            if api_settings.BLACKLIST_AFTER_ROTATION:
                try:
                    refresh.blacklist()
                except AttributeError:
                    pass
            refresh.set_jti()
            refresh.set_exp()
            refresh.set_iat()
            refresh.outstand()
            data["refresh"] = str(refresh)

        return data
