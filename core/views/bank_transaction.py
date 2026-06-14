from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets

from core.filters import BankTransactionFilter
from core.models import BankTransaction
from core.serializers import BankTransactionSerializer

from .base import get_store_for_user


class BankTransactionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = BankTransactionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = BankTransactionFilter
    lookup_url_kwarg = "bank_transaction_pk"

    def get_queryset(self):
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        return BankTransaction.objects.filter(store=store).order_by("-date")

    def perform_create(self, serializer):
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        serializer.save(store=store)
