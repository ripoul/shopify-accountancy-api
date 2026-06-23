from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.business_logic.import_orders import import_orders as upsert_orders
from core.filters import OrderFilter
from core.models import Order, OrderExpense, OrderLineItem
from core.permissions import CanManageStore
from core.serializers import OrderExpenseSerializer, OrderLineItemSerializer, OrderSerializer

from .base import get_store_for_user


@extend_schema(tags=["order"])
class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, CanManageStore]
    serializer_class = OrderSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = OrderFilter
    lookup_url_kwarg = "order_pk"
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        return (
            Order.objects.filter(store=store)
            .prefetch_related("line_items", "expenses", "discounts")
            .order_by("-processed_at")
        )

    @action(detail=False, methods=["post"], url_path="import_orders")
    def import_orders(self, request, store_pk=None):
        store = get_store_for_user(request.user, store_pk)
        external_id = request.data.get("external_id")

        if external_id:
            upsert_orders(store, external_id=external_id)
            return Response(status=status.HTTP_204_NO_CONTENT)

        last_order = Order.objects.filter(store=store).order_by("-processed_at").first()
        since = last_order.processed_at if last_order else None
        has_more = upsert_orders(store, since=since)

        return Response({"has_more": has_more})


@extend_schema(tags=["order"])
class OrderExpenseViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, CanManageStore]
    serializer_class = OrderExpenseSerializer
    lookup_url_kwarg = "expense_pk"
    lookup_value_regex = r"\d+"

    def _get_order(self):
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        return get_object_or_404(Order, store=store, pk=self.kwargs["order_pk"])

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return OrderExpense.objects.none()
        order = self._get_order()
        return OrderExpense.objects.filter(order=order, source=OrderExpense.Source.MANUAL).order_by("id")

    def perform_create(self, serializer):
        order = self._get_order()
        serializer.save(order=order, source=OrderExpense.Source.MANUAL)
        order.recompute_financials()

    def perform_update(self, serializer):
        expense = serializer.save()
        expense.order.recompute_financials()

    def perform_destroy(self, instance):
        order = instance.order
        instance.delete()
        order.recompute_financials()


@extend_schema(tags=["order"])
class OrderLineItemViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated, CanManageStore]
    serializer_class = OrderLineItemSerializer
    lookup_url_kwarg = "line_item_pk"
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return OrderLineItem.objects.none()
        store = get_store_for_user(self.request.user, self.kwargs["store_pk"])
        order = get_object_or_404(Order, store=store, pk=self.kwargs["order_pk"])
        return OrderLineItem.objects.filter(order=order)

    def perform_update(self, serializer):
        order_line_item = serializer.save()
        order_line_item.order.recompute_financials()
