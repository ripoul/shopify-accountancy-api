from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from core.filters import CashTransactionFilter
from core.models import CashTransaction
from core.permissions import CanManageStore
from core.serializers import CashTransactionSerializer

from .base import get_store_for_user


@extend_schema(tags=["cash_transaction"])
class CashTransactionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, CanManageStore]
    serializer_class = CashTransactionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = CashTransactionFilter
    lookup_url_kwarg = "cash_transaction_pk"
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return CashTransaction.objects.none()
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        return CashTransaction.objects.filter(store=store).order_by("-date")

    def perform_create(self, serializer):
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        serializer.save(store=store)
