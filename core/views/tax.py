from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets

from core.filters import TaxFilter
from core.models import Tax
from core.serializers import TaxSerializer

from .base import get_store_for_user


@extend_schema(tags=["tax"])
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
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Tax.objects.none()
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        return Tax.objects.filter(store=store).order_by("-quarter")
