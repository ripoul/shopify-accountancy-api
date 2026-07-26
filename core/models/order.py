from decimal import Decimal

from django.db import models

from .product import Product, ProductVariant
from .store import Store

AFTER_TAX_RATE = Decimal("0.134")


class Order(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="orders")
    external_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    processed_at = models.DateTimeField()
    payment_method = models.CharField(max_length=255, blank=True)
    currency_code = models.CharField(max_length=10, blank=True)
    subtotal_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    total_discounts = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    total_returns = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    net_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    cash_paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    product_purchase_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    returns_purchase_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    net_margin = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    after_tax_result = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    quarter = models.CharField(max_length=7, blank=True)
    shopify_transfer_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("store", "external_id")

    def __str__(self):
        return self.name

    def _compute_quarter(self):
        if not self.processed_at:
            return ""
        quarter = (self.processed_at.month - 1) // 3 + 1
        return f"{self.processed_at.year}/{quarter:02d}"

    def recompute_financials(self):
        purchase_cost = Decimal("0")
        for item in self.line_items.all():
            if item.distributor_price:
                purchase_cost += item.distributor_price * item.quantity

        expenses = list(self.expenses.all())
        total_expenses = sum((expense.amount for expense in expenses), Decimal("0"))
        shopify_fee = sum(
            (expense.amount for expense in expenses if expense.type == OrderExpense.Type.SHOPIFY_PAYMENT),
            Decimal("0"),
        )

        returns_total = Decimal("0")
        returns_cost = Decimal("0")
        for order_return in self.returns.all():
            returns_total += order_return.amount
            for return_line_item in order_return.line_items.all():
                line_item = return_line_item.order_line_item
                if line_item and line_item.distributor_price:
                    returns_cost += line_item.distributor_price * return_line_item.quantity

        self.product_purchase_cost = purchase_cost
        self.total_returns = returns_total
        self.returns_purchase_cost = returns_cost
        self.net_revenue = self.total_price - returns_total
        self.net_margin = self.net_revenue - total_expenses - (purchase_cost - returns_cost)
        self.after_tax_result = self.net_margin - (self.net_revenue * AFTER_TAX_RATE)
        self.shopify_transfer_amount = self.total_price - shopify_fee
        self.quarter = self._compute_quarter()
        self.save(
            update_fields=[
                "product_purchase_cost",
                "total_returns",
                "returns_purchase_cost",
                "net_revenue",
                "net_margin",
                "after_tax_result",
                "shopify_transfer_amount",
                "quarter",
                "updated_at",
            ]
        )


class OrderLineItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="line_items")
    external_id = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    distributor_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        related_name="order_line_items",
        null=True,
        blank=True,
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        related_name="order_line_items",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("order", "external_id")

    def __str__(self):
        return f"{self.title} x{self.quantity}"


class OrderExpense(models.Model):
    class Type(models.TextChoices):
        DELIVERY = "DELIVERY", "Delivery"
        PACKAGING = "PACKAGING", "Packaging"
        SHOPIFY_PAYMENT = "SHOPIFY_PAYMENT", "Shopify payment"
        OTHER = "OTHER", "Other"

    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Manual"
        AUTO = "AUTO", "Auto"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="expenses")
    type = models.CharField(max_length=20, choices=Type.choices)
    source = models.CharField(max_length=10, choices=Source.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    label = models.CharField(max_length=255, blank=True)
    external_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.type} - {self.amount}"


class OrderDiscount(models.Model):
    class Type(models.TextChoices):
        SHOPIFY_DISCOUNT = "SHOPIFY_DISCOUNT", "Shopify discount"
        STORE_CREDIT = "STORE_CREDIT", "Store credit"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="discounts")
    type = models.CharField(max_length=20, choices=Type.choices)
    external_index = models.IntegerField(null=True, blank=True)
    code = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.type} - {self.amount}"


class Return(models.Model):
    class Source(models.TextChoices):
        RETURN = "RETURN", "Return"
        REFUND = "REFUND", "Refund"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="returns")
    external_id = models.CharField(max_length=255)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.RETURN)
    name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=50, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("order", "external_id")

    def __str__(self):
        return f"{self.name} - {self.amount}"


class ReturnLineItem(models.Model):
    return_ref = models.ForeignKey(Return, on_delete=models.CASCADE, related_name="line_items")
    order_line_item = models.ForeignKey(
        OrderLineItem,
        on_delete=models.SET_NULL,
        related_name="return_line_items",
        null=True,
        blank=True,
    )
    external_id = models.CharField(max_length=255)
    title = models.CharField(max_length=255, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("return_ref", "external_id")

    def __str__(self):
        return f"{self.title} x{self.quantity}"
