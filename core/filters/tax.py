import django_filters

from core.models import Tax


class TaxFilter(django_filters.FilterSet):
    quarter = django_filters.CharFilter(field_name="quarter", lookup_expr="exact")
    has_payment = django_filters.BooleanFilter(field_name="payment_date", lookup_expr="isnull", exclude=True)

    class Meta:
        model = Tax
        fields = ["quarter"]
