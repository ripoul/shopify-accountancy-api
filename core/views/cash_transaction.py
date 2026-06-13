from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets

from core.filters import CashTransactionFilter
from core.models import CashTransaction
from core.serializers import CashTransactionSerializer

from .base import get_store_for_user


class CashTransactionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = CashTransactionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = CashTransactionFilter
    lookup_url_kwarg = "cash_transaction_pk"

    def get_queryset(self):
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        return CashTransaction.objects.filter(store=store).order_by("-date")

    def perform_create(self, serializer):
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        serializer.save(store=store, source=CashTransaction.Source.ORDER)
