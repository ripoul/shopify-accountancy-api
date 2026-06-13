from decimal import Decimal

from django.db import models

from .product import Product, ProductVariant
from .store import Store

AFTER_TAX_RATE = Decimal("0.30")


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
    cash_paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    product_purchase_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
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
            if item.variant and item.variant.distributor_price is not None:
                purchase_cost += item.variant.distributor_price * item.quantity

        expenses = list(self.expenses.all())
        total_expenses = sum((expense.amount for expense in expenses), Decimal("0"))
        shopify_fee = sum(
            (expense.amount for expense in expenses if expense.type == OrderExpense.Type.SHOPIFY_PAYMENT),
            Decimal("0"),
        )

        self.product_purchase_cost = purchase_cost
        self.net_margin = self.total_price - total_expenses - purchase_cost
        self.after_tax_result = self.net_margin - (self.total_price * AFTER_TAX_RATE)
        self.shopify_transfer_amount = self.total_price - shopify_fee
        self.quarter = self._compute_quarter()
        self.save(
            update_fields=[
                "product_purchase_cost",
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
