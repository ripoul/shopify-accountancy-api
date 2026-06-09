from rest_framework import serializers

from core.models import ProductVariant


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ["id", "external_id", "title", "price", "distributor_price"]
        read_only_fields = ["id", "external_id", "title", "price"]
