from rest_framework.permissions import BasePermission


class CanManageProductVariant(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.has_perm("core.can_manage", obj.product.store)
