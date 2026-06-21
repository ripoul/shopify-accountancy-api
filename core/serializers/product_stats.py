from decimal import Decimal

from rest_framework import serializers


class _StatsBaseMixin:
    def get_occurrence_rate(self, obj) -> str:
        total_orders = self.context.get("total_orders", 0)
        if total_orders:
            return str(round(Decimal(obj.orders_containing) / Decimal(total_orders), 4))
        return "0.0000"


class ProductStatsSerializer(_StatsBaseMixin, serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    external_id = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True, help_text="Product name")
    total_sold = serializers.IntegerField(
        read_only=True,
        help_text="Total quantity sold across all orders (Σ quantity of matching line items)",
    )
    net_gain = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        read_only=True,
        help_text="Total gain — Σ (unit_price − distributor_price) × quantity across all line items",
    )
    net_gain_per_unit = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        read_only=True,
        help_text="Average gain per unit sold (net_gain / total_sold). Returns '0.00' if total_sold is 0.",
    )
    orders_containing = serializers.IntegerField(
        read_only=True,
        help_text="Number of distinct orders that contain at least one line item for this product",
    )
    occurrence_rate = serializers.SerializerMethodField(
        help_text=(
            "Fraction of all store orders that contain this product "
            "(orders_containing / total_orders), rounded to 4 decimal places. "
            "Returns '0.0000' when the store has no orders."
        ),
    )


class ProductVariantStatsSerializer(_StatsBaseMixin, serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    external_id = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True, help_text="Variant title, e.g. 'M / Rouge'")
    product_title = serializers.CharField(
        source="product.title",
        read_only=True,
        help_text="Parent product name",
    )
    price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
        help_text="Variant retail price",
    )
    distributor_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        allow_null=True,
        read_only=True,
        help_text="Purchase price from distributor. Null if not set.",
    )
    total_sold = serializers.IntegerField(
        read_only=True,
        help_text="Total quantity sold across all orders (Σ quantity of matching line items)",
    )
    net_gain = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        read_only=True,
        help_text="Total gain — Σ (unit_price − distributor_price) × quantity across all line items",
    )
    net_gain_per_unit = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        read_only=True,
        help_text="Average gain per unit sold (net_gain / total_sold). Returns '0.00' if total_sold is 0.",
    )
    orders_containing = serializers.IntegerField(
        read_only=True,
        help_text="Number of distinct orders that contain this variant",
    )
    occurrence_rate = serializers.SerializerMethodField(
        help_text=(
            "Fraction of all store orders that contain this variant "
            "(orders_containing / total_orders), rounded to 4 decimal places. "
            "Returns '0.0000' when the store has no orders."
        ),
    )
