from decimal import Decimal

from django.db import models

from .order import Order
from .royalty import Royalty
from .store import Store
from .tax import Tax


class BankTransaction(models.Model):
    class Source(models.TextChoices):
        ORDER = "ORDER", "Order"
        PURCHASE = "PURCHASE", "Purchase"
        EMPTY_CASHBOX = "EMPTY_CASHBOX", "Empty Cashbox"
        FILL_CASHBOX = "FILL_CASHBOX", "Fill Cashbox"
        TAX = "TAX", "Tax"
        ROYALTY = "ROYALTY", "Royalty"
        ORDER_DELIVERY = "ORDER_DELIVERY", "Order Delivery"
        OTHER = "OTHER", "Other"

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="bank_transactions")
    title = models.CharField(max_length=255)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="bank_transactions",
        null=True,
        blank=True,
    )
    tax = models.OneToOneField(
        Tax,
        on_delete=models.SET_NULL,
        related_name="bank_transaction",
        null=True,
        blank=True,
    )
    royalty = models.OneToOneField(
        Royalty,
        on_delete=models.SET_NULL,
        related_name="bank_transaction",
        null=True,
        blank=True,
    )
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    source = models.CharField(max_length=50, choices=Source.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("store", "order")

    def __str__(self):
        return f"{self.source} - {self.amount}"
