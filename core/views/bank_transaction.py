from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from core.filters import BankTransactionFilter
from core.models import BankTransaction
from core.permissions import CanManageStore
from core.serializers import BankTransactionSerializer

from .base import get_store_for_user


@extend_schema(tags=["bank_transaction"])
class BankTransactionViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, CanManageStore]
    serializer_class = BankTransactionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = BankTransactionFilter
    lookup_url_kwarg = "bank_transaction_pk"
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return BankTransaction.objects.none()
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        return BankTransaction.objects.filter(store=store).order_by("-date")

    def perform_create(self, serializer):
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        serializer.save(store=store)
