from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets

from core.filters import RoyaltyFilter
from core.models import Royalty
from core.serializers import RoyaltySerializer

from .base import get_store_for_user


@extend_schema(tags=["royalty"])
class RoyaltyViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = RoyaltySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = RoyaltyFilter
    lookup_url_kwarg = "royalty_pk"
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Royalty.objects.none()
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        return Royalty.objects.filter(store=store).order_by("-quarter")
