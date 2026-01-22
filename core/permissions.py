from rest_framework.permissions import BasePermission


class IsOrgAdmin(BasePermission):
    message = "Bu işlem için Admin yetkisi gerekli."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and getattr(user, "user_type", None) == 1
        )


class IsOrgTester(BasePermission):
    message = "Bu işlem için Tester yetkisi gerekli."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and getattr(user, "user_type", None) == 3
        )


class IsOrgAdminOrTester(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        org = getattr(user, "organization", None)
        if (
            not org
            or getattr(org, "is_deleted", False)
            or not getattr(org, "is_active", True)
        ):
            return False

        return getattr(user, "user_type", None) in (1, 3)
