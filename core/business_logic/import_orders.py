from decimal import Decimal

from django.utils.dateparse import parse_datetime

from core.models import Order, OrderDiscount, OrderExpense, OrderLineItem, Product, ProductVariant
from core.shopify import get_order

SUCCESS_STATUS = "SUCCESS"
SALE_KINDS = {"SALE", "CAPTURE"}
STORE_CREDIT_GATEWAY = "store-credit"
CASH_GATEWAY = "cash"


def _money(money_set):
    if not money_set:
        return Decimal("0")
    return Decimal(money_set["shopMoney"]["amount"])


def import_orders(store, since=None, external_id=None):
    for order_data in get_order(store, since=since, external_id=external_id):
        _import_order(store, order_data)


def _import_order(store, order_data):
    transactions = order_data.get("transactions") or []
    sales = [t for t in transactions if t.get("status") == SUCCESS_STATUS and t.get("kind") in SALE_KINDS]

    cash_paid = sum(
        (_money(t.get("amountSet")) for t in sales if t.get("gateway") == CASH_GATEWAY),
        Decimal("0"),
    )

    order, _ = Order.objects.update_or_create(
        store=store,
        external_id=order_data["id"],
        defaults={
            "name": order_data["name"],
            "processed_at": parse_datetime(order_data["processedAt"]),
            "currency_code": order_data.get("currencyCode") or "",
            "subtotal_price": _money(order_data.get("subtotalPriceSet")),
            "total_discounts": _money(order_data.get("totalDiscountsSet")),
            "total_price": _money(order_data.get("totalPriceSet")),
            "payment_method": _payment_method(order_data, sales),
            "cash_paid_amount": cash_paid,
        },
    )

    _import_line_items(store, order, order_data)
    _import_shopify_fee(order, sales)
    _import_discounts(order, order_data)
    _import_store_credit(order, sales)

    order.recompute_financials()


def _payment_method(order_data, sales):
    for transaction in sales:
        if transaction.get("gateway") != STORE_CREDIT_GATEWAY:
            return transaction.get("formattedGateway") or transaction.get("gateway") or ""

    gateways = order_data.get("paymentGatewayNames") or []
    return gateways[0] if gateways else ""


def _resolve_variant(store, variant_data):
    if not variant_data:
        return None
    return ProductVariant.objects.filter(product__store=store, external_id=variant_data["id"]).first()


def _resolve_product(store, product_data):
    if not product_data:
        return None
    return Product.objects.filter(store=store, external_id=product_data["id"]).first()


def _import_line_items(store, order, order_data):
    for edge in order_data["lineItems"]["edges"]:
        node = edge["node"]
        OrderLineItem.objects.update_or_create(
            order=order,
            external_id=node["id"],
            defaults={
                "title": node["title"],
                "quantity": node["quantity"],
                "unit_price": _money(node.get("originalUnitPriceSet")),
                "variant": _resolve_variant(store, node.get("variant")),
                "product": _resolve_product(store, node.get("product")),
            },
        )


def _import_shopify_fee(order, sales):
    fee_total = Decimal("0")
    for transaction in sales:
        for fee in transaction.get("fees") or []:
            fee_total += Decimal(fee["amount"]["amount"])

    if not fee_total:
        return

    OrderExpense.objects.update_or_create(
        order=order,
        type=OrderExpense.Type.SHOPIFY_PAYMENT,
        source=OrderExpense.Source.AUTO,
        defaults={"amount": fee_total, "label": "Shopify payment fees"},
    )


def _import_discounts(order, order_data):
    applications = {}
    for edge in order_data["discountApplications"]["edges"]:
        node = edge["node"]
        applications[node["index"]] = {
            "code": node.get("code") or "",
            "title": node.get("title") or "",
            "amount": Decimal("0"),
        }

    for edge in order_data["lineItems"]["edges"]:
        for allocation in edge["node"].get("discountAllocations") or []:
            index = allocation["discountApplication"]["index"]
            if index in applications:
                applications[index]["amount"] += _money(allocation.get("allocatedAmountSet"))

    for index, info in applications.items():
        OrderDiscount.objects.update_or_create(
            order=order,
            type=OrderDiscount.Type.SHOPIFY_DISCOUNT,
            external_index=index,
            defaults={
                "code": info["code"],
                "title": info["title"],
                "amount": info["amount"],
            },
        )


def _import_store_credit(order, sales):
    credit_total = sum(
        (_money(t.get("amountSet")) for t in sales if t.get("gateway") == STORE_CREDIT_GATEWAY),
        Decimal("0"),
    )

    if not credit_total:
        return

    OrderDiscount.objects.update_or_create(
        order=order,
        type=OrderDiscount.Type.STORE_CREDIT,
        defaults={"amount": credit_total, "title": "Store credit"},
    )
