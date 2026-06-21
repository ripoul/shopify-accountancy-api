import calendar
import datetime
from decimal import Decimal

from django.db.models import Avg, Case, Count, DecimalField, ExpressionWrapper, F, IntegerField, Q, Sum, Value, When
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.filters.product_stats import ProductStatsFilter, VariantStatsFilter
from core.models import Order, Product, ProductVariant, Purchase
from core.permissions import CanManageStore
from core.serializers.product_stats import ProductStatsSerializer, ProductVariantStatsSerializer
from core.serializers.stats import DashboardStatsSerializer, QuarterHistoryItemSerializer

from .base import get_store_for_user


def _get_quarter_start(d: datetime.date) -> datetime.date:
    first_month = ((d.month - 1) // 3) * 3 + 1
    return d.replace(month=first_month, day=1)


def _get_quarter_label(d: datetime.date) -> str:
    quarter_num = (d.month - 1) // 3 + 1
    return f"{d.year}/{quarter_num:02d}"


def _get_quarter_end(quarter_start: datetime.date) -> datetime.date:
    end_month = quarter_start.month + 2
    _, last_day = calendar.monthrange(quarter_start.year, end_month)
    return quarter_start.replace(month=end_month, day=last_day)


def _iter_quarter_starts(first: datetime.date, last: datetime.date):
    """Yields quarter start dates from `first` to `last` (both inclusive)."""
    q = first
    while q <= last:
        yield q
        next_month = q.month + 3
        if next_month > 12:
            q = q.replace(year=q.year + 1, month=next_month - 12)
        else:
            q = q.replace(month=next_month)


def _get_previous_quarter_start(current_quarter_start: datetime.date) -> datetime.date:
    one_day_before = current_quarter_start - datetime.timedelta(days=1)
    return _get_quarter_start(one_day_before)


def _compute_period_stats(store, start_date: datetime.date, end_date: datetime.date, period: str) -> dict:
    agg = Order.objects.filter(
        store=store,
        processed_at__date__gte=start_date,
        processed_at__date__lte=end_date,
    ).aggregate(
        revenue=Sum("total_price"),
        profit_before_tax=Sum("net_margin"),
        profit_after_tax=Sum("after_tax_result"),
        order_count=Count("id"),
        avg_basket=Avg("total_price"),
    )

    revenue = agg["revenue"] or Decimal("0")
    profit_before_tax = agg["profit_before_tax"] or Decimal("0")
    profit_after_tax = agg["profit_after_tax"] or Decimal("0")
    order_count = agg["order_count"] or 0
    avg_basket = agg["avg_basket"] or Decimal("0")

    purchase_aggs = Purchase.objects.filter(
        store=store,
        order_date__gte=start_date,
        order_date__lte=end_date,
    ).aggregate(
        total=Sum("price"),
        non_raw_total=Sum("price", filter=Q(is_raw_material=False)),
    )
    all_purchase_total = purchase_aggs["total"] or Decimal("0")
    non_raw_purchase_total = purchase_aggs["non_raw_total"] or Decimal("0")

    return {
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "revenue": revenue,
        "profit_before_tax": profit_before_tax,
        "profit_after_tax": profit_after_tax,
        "profit_after_tax_after_purchase": profit_after_tax - non_raw_purchase_total,
        "cash_variation": revenue - all_purchase_total,
        "order_count": order_count,
        "average_profit_per_order": profit_after_tax / order_count if order_count else Decimal("0"),
        "average_basket": avg_basket,
    }


@extend_schema(tags=["stats"])
class StatsViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, CanManageStore]
    pagination_class = None

    @extend_schema(
        summary="Current quarter stats compared to same period last quarter",
        description=(
            "Returns aggregated financial metrics for the current quarter (from quarter start to today) "
            "and for the same elapsed period in the previous quarter.\n\n"
            "The **previous quarter same period** is computed by counting how many days have elapsed "
            "since the start of the current quarter, then applying that same offset to the previous quarter. "
            "This ensures an apples-to-apples comparison.\n\n"
            "**Metrics:**\n"
            "- `revenue`: Total amount paid by customers (CA) — sum of `total_price`\n"
            "- `profit_before_tax`: Revenue minus all operating expenses and COGS (`net_margin`)\n"
            "- `profit_after_tax`: Profit after 13.4% tax rate applied to revenue (`after_tax_result`)\n"
            "- `profit_after_tax_after_purchase`: Profit after tax minus non-raw-material `Purchase` records\n"
            "- `cash_variation`: Revenue minus all `Purchase` records (raw material included) — raw cash view\n"
            "- `order_count`: Number of orders\n"
            "- `average_profit_per_order`: `profit_after_tax / order_count`\n"
            "- `average_basket`: Average order value (panier moyen)"
        ),
        responses={200: DashboardStatsSerializer},
    )
    @action(detail=False, methods=["get"], url_path="current-quarter")
    def current_quarter(self, request, store_pk=None):
        store = get_store_for_user(request.user, store_pk)
        today = timezone.localdate()

        current_start = _get_quarter_start(today)
        current_period = _get_quarter_label(today)
        days_elapsed = (today - current_start).days

        prev_start = _get_previous_quarter_start(current_start)
        prev_end = prev_start + datetime.timedelta(days=days_elapsed)
        prev_period = _get_quarter_label(prev_start)

        data = {
            "current_quarter": _compute_period_stats(store, current_start, today, current_period),
            "previous_quarter": _compute_period_stats(store, prev_start, prev_end, prev_period),
        }
        return Response(DashboardStatsSerializer(data).data)

    @extend_schema(
        summary="Stats evolution across quarters",
        description=(
            "Returns aggregated financial metrics for each quarter, ordered chronologically "
            "(oldest first), covering up to **20 quarters** back or the first quarter with data, "
            "whichever is more recent.\n\n"
            "The current in-progress quarter is always included as the last item; its `end_date` "
            "is today and `is_current` is `true`. All other quarters use their full calendar "
            "end date (e.g. March 31, June 30).\n\n"
            "Returns an empty list if the store has no orders.\n\n"
            "**Metrics per quarter:**\n"
            "- `revenue`: Total revenue (CA) — sum of `total_price`\n"
            "- `profit_before_tax`: Revenue minus all operating expenses and COGS\n"
            "- `profit_after_tax`: Profit after 13.4% tax applied to revenue\n"
            "- `profit_after_tax_after_purchase`: Profit after tax minus non-raw-material purchases\n"
            "- `cash_variation`: Revenue minus all purchases including raw materials\n"
            "- `order_count`: Number of orders\n"
            "- `average_profit_per_order`: `profit_after_tax / order_count`\n"
            "- `average_basket`: Average order value (panier moyen)"
        ),
        responses={200: QuarterHistoryItemSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="quarters-history")
    def quarters_history(self, request, store_pk=None):
        store = get_store_for_user(request.user, store_pk)
        today = timezone.localdate()

        earliest_dt = (
            Order.objects.filter(store=store).order_by("processed_at").values_list("processed_at", flat=True).first()
        )
        if earliest_dt is None:
            return Response([])

        earliest_date = earliest_dt.date() if hasattr(earliest_dt, "date") else earliest_dt
        current_quarter_start = _get_quarter_start(today)
        first_quarter_start = _get_quarter_start(earliest_date)

        all_quarter_starts = list(_iter_quarter_starts(first_quarter_start, current_quarter_start))
        if len(all_quarter_starts) > 20:
            all_quarter_starts = all_quarter_starts[-20:]

        result = []
        for q_start in all_quarter_starts:
            is_current = q_start == current_quarter_start
            q_end = today if is_current else _get_quarter_end(q_start)
            period = _get_quarter_label(q_start)
            stats = _compute_period_stats(store, q_start, q_end, period)
            stats["is_current"] = is_current
            result.append(stats)

        return Response(QuarterHistoryItemSerializer(result, many=True).data)

    _DECIMAL_FIELD = DecimalField(max_digits=20, decimal_places=4)

    def _annotate_stats(self, queryset):
        """Annotate queryset with sales stats. Two passes: net_gain_per_unit depends on total_sold and net_gain."""
        return queryset.annotate(
            total_sold=Coalesce(
                Sum("order_line_items__quantity"),
                0,
                output_field=IntegerField(),
            ),
            net_gain=Coalesce(
                Sum(
                    ExpressionWrapper(
                        (F("order_line_items__unit_price") - F("order_line_items__distributor_price"))
                        * F("order_line_items__quantity"),
                        output_field=self._DECIMAL_FIELD,
                    )
                ),
                Decimal("0"),
                output_field=self._DECIMAL_FIELD,
            ),
            orders_containing=Count("order_line_items__order", distinct=True),
        ).annotate(
            net_gain_per_unit=Case(
                When(total_sold=0, then=Value(Decimal("0"), output_field=self._DECIMAL_FIELD)),
                default=ExpressionWrapper(
                    F("net_gain") / Cast(F("total_sold"), output_field=self._DECIMAL_FIELD),
                    output_field=self._DECIMAL_FIELD,
                ),
                output_field=self._DECIMAL_FIELD,
            ),
        )

    @extend_schema(
        summary="Sales statistics by product",
        description=(
            "Returns all products for the store with all-time sales statistics. "
            "Stats are aggregated from all `OrderLineItem` rows linked to any variant of each product. "
            "Results are ordered by product name by default."
        ),
        parameters=[
            OpenApiParameter(
                "name", OpenApiTypes.STR, description="Filter by product name (case-insensitive contains)."
            ),
            OpenApiParameter("collection", OpenApiTypes.INT, description="Filter by collection id."),
        ],
        responses={200: ProductStatsSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="product-stats")
    def product_stats(self, request, store_pk=None):
        store = get_store_for_user(request.user, store_pk)
        total_orders = Order.objects.filter(store=store).count()

        queryset = self._annotate_stats(Product.objects.filter(store=store)).order_by("title")

        filterset = ProductStatsFilter(request.GET, queryset=queryset, request=request)
        serializer = ProductStatsSerializer(
            filterset.qs,
            many=True,
            context={"total_orders": total_orders, "request": request},
        )
        return Response(serializer.data)

    @extend_schema(
        summary="Sales statistics by variant",
        description=(
            "Returns all product variants for the store with all-time sales statistics. "
            "Stats are computed from `OrderLineItem` rows linked to each variant. "
            "Results are ordered by product name then variant title by default."
        ),
        parameters=[
            OpenApiParameter(
                "name", OpenApiTypes.STR, description="Filter by variant title (case-insensitive contains)."
            ),
            OpenApiParameter("product", OpenApiTypes.INT, description="Filter by product id."),
            OpenApiParameter("collection", OpenApiTypes.INT, description="Filter by collection id."),
        ],
        responses={200: ProductVariantStatsSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="variant-stats")
    def variant_stats(self, request, store_pk=None):
        store = get_store_for_user(request.user, store_pk)
        total_orders = Order.objects.filter(store=store).count()

        queryset = self._annotate_stats(
            ProductVariant.objects.filter(product__store=store).select_related("product")
        ).order_by("product__title", "title")

        filterset = VariantStatsFilter(request.GET, queryset=queryset, request=request)
        serializer = ProductVariantStatsSerializer(
            filterset.qs,
            many=True,
            context={"total_orders": total_orders, "request": request},
        )
        return Response(serializer.data)
