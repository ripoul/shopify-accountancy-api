from decimal import Decimal

from django.db import models


class Store(models.Model):
    shop_domain = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    access_token = models.CharField(max_length=255)
    scopes = models.CharField(max_length=500, blank=True)
    cash_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    bank_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    royalty_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [
            ("can_manage", "Can manage store"),
        ]

    def __str__(self):
        return self.shop_domain
