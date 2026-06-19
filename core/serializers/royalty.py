from rest_framework import serializers

from core.models import Royalty


class RoyaltySerializer(serializers.ModelSerializer):
    bank_transaction = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Royalty
        fields = [
            "id",
            "quarter",
            "amount",
            "sum_after_tax_result",
            "sum_purchase_price",
            "payment_date",
            "bank_transaction",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "quarter", "sum_after_tax_result", "sum_purchase_price", "created_at", "updated_at"]

    def validate(self, data):
        if self.instance and self.instance.payment_date:
            raise serializers.ValidationError(
                "This royalty record is locked because a payment date has already been set."
            )
        return data
