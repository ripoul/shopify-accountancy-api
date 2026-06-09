from guardian.shortcuts import get_objects_for_user
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from core.models import ProductVariant, Store
from core.permissions import CanManageProductVariant
from core.serializers import ProductVariantSerializer


class ProductVariantViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated, CanManageProductVariant]
    lookup_url_kwarg = "variant_pk"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or "store_pk" not in self.kwargs:
            return ProductVariant.objects.none()

        stores = get_objects_for_user(self.request.user, "core.can_manage", Store)
        return ProductVariant.objects.select_related("product__store").filter(
            product__store__in=stores,
            product__store_id=self.kwargs["store_pk"],
        )
