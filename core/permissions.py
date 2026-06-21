from guardian.shortcuts import get_objects_for_user
from rest_framework.permissions import BasePermission

from core.models import Store


class CanManageStore(BasePermission):
    """Grants access only when the authenticated user has the `can_manage` guardian
    permission on the Store identified by `store_pk` in the URL kwargs."""

    def has_permission(self, request, view):
        store_pk = view.kwargs.get("store_pk")
        if not store_pk:
            return True
        return get_objects_for_user(request.user, "core.can_manage", Store).filter(pk=store_pk).exists()


class CanManageProductVariant(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.has_perm("core.can_manage", obj.product.store)
