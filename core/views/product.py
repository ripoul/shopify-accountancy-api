from django.db.models import Min
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from guardian.shortcuts import get_objects_for_user
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.business_logic.import_products import import_products as upsert_products
from core.filters import ProductFilter
from core.models import Collection, Product, Store
from core.serializers import CollectionSerializer, ProductSerializer


def _get_store_for_user(user, store_pk):
    return get_object_or_404(
        get_objects_for_user(user, "core.can_manage", Store),
        pk=store_pk,
    )


class ProductViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProductFilter

    def get_queryset(self):
        store = _get_store_for_user(self.request.user, self.kwargs["store_pk"])
        return (
            Product.objects.filter(store=store)
            .prefetch_related("collections", "variants")
            .annotate(
                min_price=Min("variants__price"),
                min_collection_title=Min("collections__title"),
            )
            .order_by("title")
        )

    @action(detail=False, methods=["post"], url_path="import_products")
    def import_products(self, request, store_pk=None):
        store = _get_store_for_user(request.user, store_pk)
        upsert_products(store)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CollectionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = CollectionSerializer

    def get_queryset(self):
        store = _get_store_for_user(self.request.user, self.kwargs["store_pk"])
        return Collection.objects.filter(store=store).order_by("title")
