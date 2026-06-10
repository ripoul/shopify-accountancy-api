from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets

from core.filters import PurchaseFilter
from core.models import Purchase
from core.serializers import PurchaseSerializer

from .base import get_store_for_user


class PurchaseViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = PurchaseSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = PurchaseFilter
    lookup_url_kwarg = "purchase_pk"

    def get_queryset(self):
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        return Purchase.objects.filter(store=store).select_related("supplier").order_by("-order_date")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if "store_pk" in self.kwargs:
            context["store"] = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        return context

    def perform_create(self, serializer):
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        serializer.save(store=store)
