from rest_framework import serializers

from core.models import BankTransaction


class BankTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankTransaction
        fields = ["id", "title", "date", "amount", "source", "order", "created_at", "updated_at"]
        read_only_fields = ["id", "order", "created_at", "updated_at"]
