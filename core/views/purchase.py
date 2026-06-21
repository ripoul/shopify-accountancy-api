from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from core.filters import PurchaseFilter
from core.models import Purchase
from core.permissions import CanManageStore
from core.serializers import PurchaseSerializer

from .base import get_store_for_user


@extend_schema(tags=["purchase"])
class PurchaseViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, CanManageStore]
    serializer_class = PurchaseSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = PurchaseFilter
    lookup_url_kwarg = "purchase_pk"
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Purchase.objects.none()
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
