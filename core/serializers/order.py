from rest_framework import serializers

from core.models import Order, OrderDiscount, OrderExpense, OrderLineItem


class OrderLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderLineItem
        fields = ["id", "external_id", "title", "quantity", "unit_price", "distributor_price", "variant", "product"]
        read_only_fields = ["id", "external_id", "title", "quantity", "unit_price", "variant", "product"]


class OrderDiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderDiscount
        fields = ["id", "type", "external_index", "code", "title", "amount"]
        read_only_fields = fields


class OrderExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderExpense
        fields = ["id", "type", "source", "amount", "label", "created_at", "updated_at"]
        read_only_fields = ["id", "source", "created_at", "updated_at"]

    def validate_type(self, value):
        if value == OrderExpense.Type.SHOPIFY_PAYMENT:
            raise serializers.ValidationError("Shopify payment fees are managed automatically.")
        return value


class OrderSerializer(serializers.ModelSerializer):
    line_items = OrderLineItemSerializer(many=True, read_only=True)
    expenses = OrderExpenseSerializer(many=True, read_only=True)
    discounts = OrderDiscountSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "external_id",
            "name",
            "processed_at",
            "payment_method",
            "currency_code",
            "subtotal_price",
            "total_discounts",
            "total_price",
            "cash_paid_amount",
            "product_purchase_cost",
            "net_margin",
            "after_tax_result",
            "quarter",
            "shopify_transfer_amount",
            "line_items",
            "expenses",
            "discounts",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
