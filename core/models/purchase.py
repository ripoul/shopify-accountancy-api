from django.db import models

from .store import Store
from .supplier import Supplier


class Purchase(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="purchases")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchases")
    order_number = models.CharField(max_length=255, blank=True)
    order_date = models.DateField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_raw_material = models.BooleanField(default=False)
    reception_date = models.DateField(null=True, blank=True)
    reception_checked = models.BooleanField(default=False)
    has_supporting_documents = models.BooleanField(default=False)
    claim_text = models.TextField(null=True, blank=True)
    claim_date = models.DateField(null=True, blank=True)
    supplier_return_text = models.TextField(null=True, blank=True)
    claim_closed_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.supplier.name} - {self.order_date}"
