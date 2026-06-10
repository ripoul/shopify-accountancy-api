from rest_framework import serializers

from core.models import Purchase, Supplier


class PurchaseSerializer(serializers.ModelSerializer):
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.none())

    class Meta:
        model = Purchase
        fields = [
            "id",
            "supplier",
            "order_number",
            "order_date",
            "price",
            "is_raw_material",
            "reception_date",
            "reception_checked",
            "has_supporting_documents",
            "claim_text",
            "claim_date",
            "supplier_return_text",
            "claim_closed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        store = self.context.get("store")
        if store is not None:
            self.fields["supplier"].queryset = Supplier.objects.filter(store=store)
