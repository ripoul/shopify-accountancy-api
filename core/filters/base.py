import django_filters


class StableOrderingFilter(django_filters.OrderingFilter):
    """OrderingFilter that appends `-id` so rows with equal sort values keep a stable order across pages."""

    def filter(self, qs, value):
        qs = super().filter(qs, value)
        if value:
            qs = qs.order_by(*qs.query.order_by, "-id")
        return qs
