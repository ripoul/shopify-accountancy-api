from rest_framework import serializers

from core.models import CashTransaction


class CashTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashTransaction
        fields = ["id", "title", "date", "amount", "source", "order", "created_at", "updated_at"]
        read_only_fields = ["id", "source", "order", "created_at", "updated_at"]
