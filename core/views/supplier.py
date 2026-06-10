from rest_framework import mixins, viewsets

from core.models import Supplier
from core.serializers import SupplierSerializer

from .base import get_store_for_user


class SupplierViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SupplierSerializer
    lookup_url_kwarg = "supplier_pk"

    def get_queryset(self):
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        return Supplier.objects.filter(store=store).order_by("name")

    def perform_create(self, serializer):
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        serializer.save(store=store)
