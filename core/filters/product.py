import django_filters

from core.models import Product


class ProductFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name="title", lookup_expr="icontains")
    collection = django_filters.NumberFilter(field_name="collections__id")
    ordering = django_filters.OrderingFilter(
        fields={
            "title": "name",
            "min_price": "price",
            "min_collection_title": "collection",
        }
    )

    class Meta:
        model = Product
        fields = ["name", "collection"]
