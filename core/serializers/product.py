from rest_framework import serializers

from core.models import Collection, Product

from .product_variant import ProductVariantSerializer


class CollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collection
        fields = ["id", "external_id", "title"]
        read_only_fields = fields


class ProductSerializer(serializers.ModelSerializer):
    collections = serializers.SerializerMethodField()
    variants = ProductVariantSerializer(many=True, read_only=True)

    def get_collections(self, obj) -> list[str]:
        return [c.title for c in obj.collections.all()]

    class Meta:
        model = Product
        fields = ["id", "external_id", "title", "collections", "variants", "created_at", "updated_at"]
        read_only_fields = fields
