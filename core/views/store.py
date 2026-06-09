from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.business_logic.import_products import import_products
from core.models import Store
from core.serializers import StoreConnectSerializer, StoreInstallSerializer, StoreSerializer
from core.shopify import build_authorization_url, exchange_shopify_code


class StoreViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return StoreConnectSerializer
        if self.action == "install":
            return StoreInstallSerializer
        return StoreSerializer

    def get_queryset(self):
        return get_objects_for_user(self.request.user, "core.can_manage", Store).order_by("id")

    def create(self, request, *args, **kwargs):
        serializer = StoreConnectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shop = serializer.validated_data["shop"]

        try:
            shopify_data = exchange_shopify_code(shop, dict(request.data))
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        store, _ = Store.objects.update_or_create(
            shop_domain=shop,
            defaults={
                "name": shopify_data["name"],
                "access_token": shopify_data["access_token"],
                "scopes": shopify_data.get("scopes", ""),
            },
        )

        assign_perm("can_manage", request.user, store)

        return Response(StoreSerializer(store).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="import_products")
    def import_products(self, request, pk=None):
        store = self.get_object()
        import_products(store)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="install")
    def install(self, request):
        serializer = StoreInstallSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        shop = serializer.validated_data["shop"]

        try:
            authorization_url = build_authorization_url(shop, request.query_params.dict())
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"authorization_url": authorization_url})
