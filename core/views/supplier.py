from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from core.models import Supplier
from core.permissions import CanManageStore
from core.serializers import SupplierSerializer

from .base import get_store_for_user


@extend_schema(tags=["supplier"])
class SupplierViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, CanManageStore]
    serializer_class = SupplierSerializer
    lookup_url_kwarg = "supplier_pk"
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Supplier.objects.none()
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        return Supplier.objects.filter(store=store).order_by("name")

    def perform_create(self, serializer):
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        serializer.save(store=store)
