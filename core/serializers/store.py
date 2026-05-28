from rest_framework import serializers

from core.models import Store


class StoreConnectSerializer(serializers.Serializer):
    shop = serializers.CharField(help_text="Domaine Shopify, ex: ma-boutique.myshopify.com")
    code = serializers.CharField(help_text="Code OAuth fourni par Shopify")
    hmac = serializers.CharField(help_text="Signature HMAC fournie par Shopify")
    state = serializers.CharField(help_text="Nonce généré lors du démarrage du flow OAuth")
    timestamp = serializers.CharField(help_text="Timestamp fourni par Shopify")


class StoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["id", "shop_domain", "name", "scopes", "created_at", "updated_at"]
        read_only_fields = fields
