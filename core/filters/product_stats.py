import django_filters

from core.models import Product, ProductVariant


class ProductStatsFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name="title", lookup_expr="icontains")
    collection = django_filters.NumberFilter(field_name="collections__id")

    class Meta:
        model = Product
        fields = ["name", "collection"]


class VariantStatsFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name="product__title", lookup_expr="icontains")
    product = django_filters.NumberFilter(field_name="product__id")
    collection = django_filters.NumberFilter(field_name="product__collections__id")

    class Meta:
        model = ProductVariant
        fields = ["name", "product", "collection"]
