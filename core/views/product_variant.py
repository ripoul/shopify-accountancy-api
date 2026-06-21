from drf_spectacular.utils import extend_schema
from guardian.shortcuts import get_objects_for_user
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from core.models import ProductVariant, Store
from core.permissions import CanManageProductVariant, CanManageStore
from core.serializers import ProductVariantSerializer


@extend_schema(tags=["product_variant"])
class ProductVariantViewSet(mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = ProductVariantSerializer
    permission_classes = [IsAuthenticated, CanManageStore, CanManageProductVariant]
    lookup_url_kwarg = "variant_pk"
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or "store_pk" not in self.kwargs:
            return ProductVariant.objects.none()

        stores = get_objects_for_user(self.request.user, "core.can_manage", Store)
        return ProductVariant.objects.select_related("product__store").filter(
            product__store__in=stores,
            product__store_id=self.kwargs["store_pk"],
        )
