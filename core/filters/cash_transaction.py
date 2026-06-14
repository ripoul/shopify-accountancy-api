import django_filters

from core.models import CashTransaction


class CashTransactionFilter(django_filters.FilterSet):
    date_after = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_before = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    ordering = django_filters.OrderingFilter(
        fields={
            "date": "date",
            "amount": "amount",
        }
    )

    class Meta:
        model = CashTransaction
        fields = []
