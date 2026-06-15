from rest_framework import serializers

from core.models import Tax


class TaxSerializer(serializers.ModelSerializer):
    bank_transaction = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Tax
        fields = ["id", "quarter", "amount", "payment_date", "bank_transaction", "created_at", "updated_at"]
        read_only_fields = ["id", "quarter", "created_at", "updated_at"]

    def validate(self, data):
        if self.instance and self.instance.payment_date:
            raise serializers.ValidationError("This tax record is locked because a payment date has already been set.")
        return data
