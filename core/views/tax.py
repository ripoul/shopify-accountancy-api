from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets

from core.filters import TaxFilter
from core.models import Tax
from core.serializers import TaxSerializer

from .base import get_store_for_user


class TaxViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = TaxSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = TaxFilter
    lookup_url_kwarg = "tax_pk"

    def get_queryset(self):
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        return Tax.objects.filter(store=store).order_by("-quarter")
