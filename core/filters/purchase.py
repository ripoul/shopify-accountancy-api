import django_filters

from core.models import Purchase


class PurchaseFilter(django_filters.FilterSet):
    supplier = django_filters.NumberFilter(field_name="supplier__id")
    order_number = django_filters.CharFilter(field_name="order_number", lookup_expr="icontains")
    ordering = django_filters.OrderingFilter(
        fields={
            "order_date": "order_date",
            "supplier__name": "supplier",
            "price": "price",
        }
    )

    class Meta:
        model = Purchase
        fields = ["supplier", "order_number"]
