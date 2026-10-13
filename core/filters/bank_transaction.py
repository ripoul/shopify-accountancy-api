import django_filters

from core.models import BankTransaction

from .base import StableOrderingFilter


class BankTransactionFilter(django_filters.FilterSet):
    source = django_filters.ChoiceFilter(field_name="source", choices=BankTransaction.Source.choices)
    date_after = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_before = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    ordering = StableOrderingFilter(
        fields={
            "date": "date",
            "amount": "amount",
        }
    )

    class Meta:
        model = BankTransaction
        fields = ["source"]
