from decimal import Decimal

from django.db import models

from .store import Store


class Royalty(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="royalties")
    quarter = models.CharField(max_length=7)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    sum_after_tax_result = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    sum_purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    payment_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("store", "quarter")

    def __str__(self):
        return f"Royalty {self.quarter} - {self.amount}"
