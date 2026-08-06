from rest_framework import serializers


class QuarterStatsSerializer(serializers.Serializer):
    period = serializers.CharField(help_text="Quarter identifier, e.g. '2026/02'")
    start_date = serializers.DateField(help_text="First day of the period")
    end_date = serializers.DateField(help_text="Last day of the period (inclusive)")
    revenue = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Total revenue (CA): sum of total_price on orders",
    )
    profit_before_tax = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Net margin: revenue minus all operating expenses and COGS, before tax",
    )
    profit_after_tax = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Profit after 13.4% tax applied to revenue",
    )
    profit_after_tax_after_purchase = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Profit after tax minus non-raw-material Purchase records in the period",
    )
    cash_variation = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Revenue (CA) minus all Purchase records including raw materials — raw cash view",
    )
    order_count = serializers.IntegerField(help_text="Number of orders in the period")
    average_profit_per_order = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="profit_after_tax divided by order_count",
    )
    average_basket = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Average order value (panier moyen)",
    )


class QuarterHistoryItemSerializer(QuarterStatsSerializer):
    is_current = serializers.BooleanField(
        help_text="True if this is the current in-progress quarter (end_date is today, not the calendar quarter end)"
    )


class DashboardStatsSerializer(serializers.Serializer):
    current_quarter = QuarterStatsSerializer(help_text="Stats for the current quarter up to today")
    previous_quarter = QuarterStatsSerializer(help_text="Stats for the same elapsed period in the previous quarter")


class TreasuryStatsSerializer(serializers.Serializer):
    bank_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Current bank balance (Store.bank_amount)",
    )
    cash_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Current cash register balance (Store.cash_amount)",
    )
    unpaid_taxes_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Sum of Tax records with no payment_date set yet",
    )
    unpaid_royalties_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Sum of Royalty records with no payment_date set yet",
    )
    fixed_costs_reserve = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Configured reserve covering ~3 months of fixed costs (Store.fixed_costs_reserve)",
    )
    investable_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=(
            "bank_amount minus unpaid_taxes_amount, unpaid_royalties_amount and fixed_costs_reserve. "
            "Can be negative if unpaid dues and the reserve exceed the bank balance."
        ),
    )
