import django_filters

from core.models import Order


class OrderFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    quarter = django_filters.CharFilter(field_name="quarter", lookup_expr="exact")
    processed_after = django_filters.DateTimeFilter(field_name="processed_at", lookup_expr="gte")
    processed_before = django_filters.DateTimeFilter(field_name="processed_at", lookup_expr="lte")
    ordering = django_filters.OrderingFilter(
        fields={
            "processed_at": "processed_at",
            "total_price": "total_price",
            "net_margin": "net_margin",
        }
    )

    class Meta:
        model = Order
        fields = ["name", "quarter"]
