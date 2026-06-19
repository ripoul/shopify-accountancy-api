from decimal import Decimal

from django.db.models import Sum

from core.models import Order, Purchase, Royalty


def _quarter_months(quarter):
    q = int(quarter.split("/")[1])
    start = (q - 1) * 3 + 1
    return list(range(start, start + 3))


def compute_royalty_breakdown(store, quarter):
    """Return (sum_after_tax_result, sum_purchase_price, royalty_amount)."""
    year = int(quarter.split("/")[0])
    months = _quarter_months(quarter)

    order_total = Order.objects.filter(store=store, quarter=quarter).aggregate(total=Sum("after_tax_result"))[
        "total"
    ] or Decimal("0")
    purchase_total = Purchase.objects.filter(
        store=store, order_date__year=year, order_date__month__in=months
    ).aggregate(total=Sum("price"))["total"] or Decimal("0")

    base = order_total - purchase_total
    amount = max(Decimal("0"), (base * store.royalty_rate / Decimal("100")).quantize(Decimal("0.01")))
    return order_total, purchase_total, amount


def recalculate_royalty_for_quarter(store, quarter):
    try:
        royalty = Royalty.objects.get(store=store, quarter=quarter)
        if royalty.payment_date:
            return
    except Royalty.DoesNotExist:
        pass

    order_total, purchase_total, amount = compute_royalty_breakdown(store, quarter)
    Royalty.objects.update_or_create(
        store=store,
        quarter=quarter,
        defaults={
            "amount": amount,
            "sum_after_tax_result": order_total,
            "sum_purchase_price": purchase_total,
        },
    )
