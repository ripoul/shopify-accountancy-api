from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Store
from core.serializers import StoreConnectSerializer, StoreSerializer
from core.services import exchange_shopify_code


class StoreViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return StoreConnectSerializer
        return StoreSerializer

    def get_queryset(self):
        return get_objects_for_user(self.request.user, "core.can_manage", Store).order_by("id")

    def create(self, request, *args, **kwargs):
        serializer = StoreConnectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        params = serializer.validated_data
        shop = params["shop"]

        try:
            shopify_data = exchange_shopify_code(shop, params)
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
