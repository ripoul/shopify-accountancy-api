from decimal import Decimal

from django.db import models

from .order import Order
from .store import Store


class CashTransaction(models.Model):
    class Source(models.TextChoices):
        ORDER = "ORDER", "Order"
        ADD_MONEY = "ADD_MONEY", "Add Money"
        WITHDRAW_MONEY = "WITHDRAW_MONEY", "Withdraw Money"
        OTHER = "OTHER", "Other"

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="cash_transactions")
    title = models.CharField(max_length=255)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="cash_transactions",
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
