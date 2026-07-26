from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from core.business_logic.import_orders import import_orders
from core.models import (
    Order,
    OrderDiscount,
    OrderExpense,
    OrderLineItem,
    Product,
    ProductVariant,
    Return,
    ReturnLineItem,
    Store,
)


def _money(amount):
    return {"shopMoney": {"amount": amount}}


def _transaction(
    kind="SALE", status="SUCCESS", gateway="shopify", formatted_gateway="Shopify", amount="29.99", fees=None
):
    return {
        "kind": kind,
        "status": status,
        "gateway": gateway,
        "formattedGateway": formatted_gateway,
        "manualPaymentGateway": None,
        "amountSet": _money(amount),
        "fees": fees or [],
    }


def _return_node(return_id="gid://shopify/Return/1", name="#1001-R1", status="CLOSED", return_line_items=None):
    return {
        "node": {
            "id": return_id,
            "name": name,
            "status": status,
            "returnLineItems": {"edges": return_line_items or []},
        }
    }


def _return_line_item(rli_id, line_item_id, quantity=1, amount="29.99"):
    return {
        "node": {
            "id": rli_id,
            "quantity": quantity,
            "withCodeDiscountedTotalPriceSet": _money(amount),
            "fulfillmentLineItem": {"lineItem": {"id": line_item_id}},
        }
    }


def _refund_node(refund_id="gid://shopify/Refund/1", refund_line_items=None, return_id=None):
    return {
        "id": refund_id,
        "return": {"id": return_id} if return_id else None,
        "refundLineItems": {"edges": refund_line_items or []},
    }


def _refund_line_item(rli_id, line_item_id, quantity=1, amount="29.99"):
    return {
        "node": {
            "id": rli_id,
            "quantity": quantity,
            "subtotalSet": _money(amount),
            "lineItem": {"id": line_item_id},
        }
    }


def _order_data(
    order_id="gid://shopify/Order/1",
    name="#1001",
    processed_at="2024-03-15T10:00:00Z",
    total_price="29.99",
    subtotal_price="29.99",
    total_discounts="0.00",
    transactions=None,
    line_items=None,
    discount_applications=None,
    currency_code="EUR",
    payment_gateway_names=None,
    returns=None,
    refunds=None,
):
    return {
        "id": order_id,
        "name": name,
        "processedAt": processed_at,
        "currencyCode": currency_code,
        "paymentGatewayNames": payment_gateway_names or ["shopify"],
        "subtotalPriceSet": _money(subtotal_price),
        "totalPriceSet": _money(total_price),
        "totalDiscountsSet": _money(total_discounts),
        "lineItems": {"edges": line_items or []},
        "discountApplications": {"edges": discount_applications or []},
        "transactions": transactions if transactions is not None else [_transaction()],
        "returns": {"edges": returns or []},
        "refunds": refunds or [],
    }


class ImportOrdersTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
        )

    def _run(self, orders):
        with patch("core.business_logic.import_orders.get_order", return_value=(orders, False)):
            import_orders(self.store)

    def test_creates_order(self):
        self._run([_order_data()])

        self.assertEqual(Order.objects.filter(store=self.store).count(), 1)
        order = Order.objects.get(store=self.store)
        self.assertEqual(order.name, "#1001")
        self.assertEqual(order.external_id, "gid://shopify/Order/1")
        self.assertEqual(order.currency_code, "EUR")
        self.assertEqual(order.total_price, Decimal("29.99"))

    def test_upserts_existing_order(self):
        Order.objects.create(
            store=self.store,
            external_id="gid://shopify/Order/1",
            name="#OLD",
            processed_at="2024-01-01T00:00:00Z",
            total_price=Decimal("10.00"),
        )

        self._run([_order_data(total_price="29.99")])

        self.assertEqual(Order.objects.filter(store=self.store).count(), 1)
        order = Order.objects.get(store=self.store)
        self.assertEqual(order.name, "#1001")
        self.assertEqual(order.total_price, Decimal("29.99"))

    def test_creates_line_item(self):
        line_items = [
            {
                "node": {
                    "id": "gid://shopify/LineItem/1",
                    "title": "T-shirt",
                    "quantity": 2,
                    "variant": None,
                    "product": None,
                    "originalUnitPriceSet": _money("29.99"),
                    "discountAllocations": [],
                }
            }
        ]
        self._run([_order_data(line_items=line_items)])

        order = Order.objects.get(store=self.store)
        self.assertEqual(order.line_items.count(), 1)
        item = order.line_items.first()
        self.assertEqual(item.title, "T-shirt")
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, Decimal("29.99"))

    def test_resolves_variant_in_line_item(self):
        product = Product.objects.create(store=self.store, external_id="gid://shopify/Product/1", title="T-shirt")
        variant = ProductVariant.objects.create(
            product=product, external_id="gid://shopify/ProductVariant/1", title="M", price="29.99"
        )
        line_items = [
            {
                "node": {
                    "id": "gid://shopify/LineItem/1",
                    "title": "T-shirt",
                    "quantity": 1,
                    "variant": {"id": "gid://shopify/ProductVariant/1"},
                    "product": {"id": "gid://shopify/Product/1"},
                    "originalUnitPriceSet": _money("29.99"),
                    "discountAllocations": [],
                }
            }
        ]
        self._run([_order_data(line_items=line_items)])

        item = OrderLineItem.objects.get(external_id="gid://shopify/LineItem/1")
        self.assertEqual(item.variant, variant)
        self.assertEqual(item.product, product)
        self.assertEqual(item.title, "T-shirt - M")

    def test_default_title_variant_keeps_plain_title(self):
        product = Product.objects.create(store=self.store, external_id="gid://shopify/Product/1", title="Mug")
        ProductVariant.objects.create(
            product=product, external_id="gid://shopify/ProductVariant/1", title="Default Title", price="9.99"
        )
        line_items = [
            {
                "node": {
                    "id": "gid://shopify/LineItem/1",
                    "title": "Mug",
                    "quantity": 1,
                    "variant": {"id": "gid://shopify/ProductVariant/1"},
                    "product": {"id": "gid://shopify/Product/1"},
                    "originalUnitPriceSet": _money("9.99"),
                    "discountAllocations": [],
                }
            }
        ]
        self._run([_order_data(line_items=line_items)])

        item = OrderLineItem.objects.get(external_id="gid://shopify/LineItem/1")
        self.assertEqual(item.title, "Mug")

    def test_missing_variant_sets_null(self):
        line_items = [
            {
                "node": {
                    "id": "gid://shopify/LineItem/1",
                    "title": "Unknown item",
                    "quantity": 1,
                    "variant": {"id": "gid://shopify/ProductVariant/999"},
                    "product": None,
                    "originalUnitPriceSet": _money("10.00"),
                    "discountAllocations": [],
                }
            }
        ]
        self._run([_order_data(line_items=line_items)])

        item = OrderLineItem.objects.get(external_id="gid://shopify/LineItem/1")
        self.assertIsNone(item.variant)

    def test_imports_shopify_fee(self):
        txn = _transaction(fees=[{"amount": {"amount": "0.59"}}])
        self._run([_order_data(transactions=[txn])])

        order = Order.objects.get(store=self.store)
        expense = order.expenses.get(type=OrderExpense.Type.SHOPIFY_PAYMENT)
        self.assertEqual(expense.amount, Decimal("0.59"))
        self.assertEqual(expense.source, OrderExpense.Source.AUTO)

    def test_no_shopify_fee_expense_when_zero(self):
        txn = _transaction(fees=[])
        self._run([_order_data(transactions=[txn])])

        order = Order.objects.get(store=self.store)
        self.assertFalse(order.expenses.filter(type=OrderExpense.Type.SHOPIFY_PAYMENT).exists())

    def test_shopify_fee_accumulates_across_transactions(self):
        txns = [
            _transaction(fees=[{"amount": {"amount": "0.30"}}]),
            _transaction(fees=[{"amount": {"amount": "0.20"}}]),
        ]
        self._run([_order_data(transactions=txns)])

        order = Order.objects.get(store=self.store)
        expense = order.expenses.get(type=OrderExpense.Type.SHOPIFY_PAYMENT)
        self.assertEqual(expense.amount, Decimal("0.50"))

    def test_imports_discount_code(self):
        discount_applications = [
            {"node": {"__typename": "DiscountCodeApplication", "index": 0, "code": "PROMO10", "title": ""}}
        ]
        line_items = [
            {
                "node": {
                    "id": "gid://shopify/LineItem/1",
                    "title": "T-shirt",
                    "quantity": 1,
                    "variant": None,
                    "product": None,
                    "originalUnitPriceSet": _money("29.99"),
                    "discountAllocations": [
                        {"allocatedAmountSet": _money("3.00"), "discountApplication": {"index": 0}}
                    ],
                }
            }
        ]
        self._run([_order_data(line_items=line_items, discount_applications=discount_applications)])

        order = Order.objects.get(store=self.store)
        discount = order.discounts.get(type=OrderDiscount.Type.SHOPIFY_DISCOUNT)
        self.assertEqual(discount.code, "PROMO10")
        self.assertEqual(discount.amount, Decimal("3.00"))
        self.assertEqual(discount.external_index, 0)

    def test_imports_store_credit(self):
        txns = [
            _transaction(gateway="store-credit", amount="5.00"),
        ]
        self._run([_order_data(transactions=txns)])

        order = Order.objects.get(store=self.store)
        credit = order.discounts.get(type=OrderDiscount.Type.STORE_CREDIT)
        self.assertEqual(credit.amount, Decimal("5.00"))
        self.assertEqual(credit.title, "Store credit")

    def test_no_store_credit_when_zero(self):
        self._run([_order_data(transactions=[_transaction()])])

        order = Order.objects.get(store=self.store)
        self.assertFalse(order.discounts.filter(type=OrderDiscount.Type.STORE_CREDIT).exists())

    def test_payment_method_from_formatted_gateway(self):
        txn = _transaction(gateway="shopify", formatted_gateway="Shopify Payments")
        self._run([_order_data(transactions=[txn])])

        order = Order.objects.get(store=self.store)
        self.assertEqual(order.payment_method, "Shopify Payments")

    def test_payment_method_skips_store_credit_gateway(self):
        txns = [
            _transaction(gateway="store-credit", formatted_gateway="Store Credit", amount="5.00"),
            _transaction(gateway="shopify", formatted_gateway="Shopify Payments", amount="24.99"),
        ]
        self._run([_order_data(transactions=txns)])

        order = Order.objects.get(store=self.store)
        self.assertEqual(order.payment_method, "Shopify Payments")

    def test_payment_method_falls_back_to_gateway_names(self):
        txns = [_transaction(gateway="store-credit", formatted_gateway="Store Credit")]
        self._run([_order_data(transactions=txns, payment_gateway_names=["paypal"])])

        order = Order.objects.get(store=self.store)
        self.assertEqual(order.payment_method, "paypal")

    def test_cash_paid_amount(self):
        txns = [
            _transaction(gateway="cash", formatted_gateway="Cash", amount="10.00"),
            _transaction(gateway="shopify", formatted_gateway="Shopify Payments", amount="19.99"),
        ]
        self._run([_order_data(transactions=txns)])

        order = Order.objects.get(store=self.store)
        self.assertEqual(order.cash_paid_amount, Decimal("10.00"))

    def test_failed_transaction_not_counted(self):
        txns = [
            _transaction(status="FAILURE", gateway="cash", amount="10.00"),
            _transaction(status="SUCCESS", gateway="shopify", amount="29.99"),
        ]
        self._run([_order_data(transactions=txns)])

        order = Order.objects.get(store=self.store)
        self.assertEqual(order.cash_paid_amount, Decimal("0"))

    def test_non_sale_kind_not_counted_for_cash(self):
        txns = [
            _transaction(kind="REFUND", status="SUCCESS", gateway="cash", amount="10.00"),
        ]
        self._run([_order_data(transactions=txns)])

        order = Order.objects.get(store=self.store)
        self.assertEqual(order.cash_paid_amount, Decimal("0"))

    def test_recompute_financials_called(self):
        with patch("core.business_logic.import_orders.get_order", return_value=([_order_data()], False)):
            with patch.object(Order, "recompute_financials") as mock_recompute:
                import_orders(self.store)
                mock_recompute.assert_called_once()

    def test_imports_multiple_orders(self):
        self._run(
            [
                _order_data(order_id="gid://shopify/Order/1", name="#1001"),
                _order_data(order_id="gid://shopify/Order/2", name="#1002"),
            ]
        )

        self.assertEqual(Order.objects.filter(store=self.store).count(), 2)

    def _order_with_return(self, quantity=1, amount="10.00"):
        line_items = [
            {
                "node": {
                    "id": "gid://shopify/LineItem/1",
                    "title": "T-shirt",
                    "quantity": 2,
                    "variant": None,
                    "product": None,
                    "originalUnitPriceSet": _money("10.00"),
                    "discountAllocations": [],
                }
            }
        ]
        returns = [
            _return_node(
                return_line_items=[
                    _return_line_item(
                        "gid://shopify/ReturnLineItem/1",
                        "gid://shopify/LineItem/1",
                        quantity=quantity,
                        amount=amount,
                    )
                ]
            )
        ]
        return _order_data(total_price="20.00", line_items=line_items, returns=returns)

    def test_creates_return(self):
        self._run([self._order_with_return(amount="10.00")])

        order = Order.objects.get(store=self.store)
        self.assertEqual(order.returns.count(), 1)
        order_return = order.returns.first()
        self.assertEqual(order_return.external_id, "gid://shopify/Return/1")
        self.assertEqual(order_return.name, "#1001-R1")
        self.assertEqual(order_return.status, "CLOSED")
        self.assertEqual(order_return.amount, Decimal("10.00"))

    def test_creates_return_line_item_linked_to_order_line_item(self):
        self._run([self._order_with_return(quantity=1, amount="10.00")])

        return_line_item = ReturnLineItem.objects.get(external_id="gid://shopify/ReturnLineItem/1")
        self.assertEqual(return_line_item.quantity, 1)
        self.assertEqual(return_line_item.amount, Decimal("10.00"))
        self.assertEqual(return_line_item.order_line_item.external_id, "gid://shopify/LineItem/1")
        self.assertEqual(return_line_item.title, "T-shirt")

    def test_return_amount_sums_line_items(self):
        returns = [
            _return_node(
                return_line_items=[
                    _return_line_item("gid://shopify/ReturnLineItem/1", "gid://shopify/LineItem/1", amount="4.00"),
                    _return_line_item("gid://shopify/ReturnLineItem/2", "gid://shopify/LineItem/1", amount="6.00"),
                ]
            )
        ]
        self._run([_order_data(total_price="20.00", returns=returns)])

        order_return = Return.objects.get(external_id="gid://shopify/Return/1")
        self.assertEqual(order_return.amount, Decimal("10.00"))

    def test_return_line_item_null_when_line_item_missing(self):
        returns = [
            _return_node(
                return_line_items=[
                    _return_line_item("gid://shopify/ReturnLineItem/1", "gid://shopify/LineItem/999", amount="10.00")
                ]
            )
        ]
        self._run([_order_data(total_price="20.00", returns=returns)])

        return_line_item = ReturnLineItem.objects.get(external_id="gid://shopify/ReturnLineItem/1")
        self.assertIsNone(return_line_item.order_line_item)

    def test_return_import_is_idempotent(self):
        order_data = self._order_with_return(amount="10.00")
        self._run([order_data])
        self._run([order_data])

        self.assertEqual(Return.objects.filter(external_id="gid://shopify/Return/1").count(), 1)
        self.assertEqual(ReturnLineItem.objects.filter(external_id="gid://shopify/ReturnLineItem/1").count(), 1)

    def test_return_updates_order_financials(self):
        self._run([self._order_with_return(quantity=1, amount="10.00")])

        order = Order.objects.get(store=self.store)
        self.assertEqual(order.total_returns, Decimal("10.00"))
        self.assertEqual(order.net_revenue, Decimal("10.00"))

    def test_return_source_defaults_to_return(self):
        self._run([self._order_with_return(amount="10.00")])

        order_return = Return.objects.get(external_id="gid://shopify/Return/1")
        self.assertEqual(order_return.source, Return.Source.RETURN)

    def _order_with_refund(self, quantity=1, amount="10.00", return_id=None):
        line_items = [
            {
                "node": {
                    "id": "gid://shopify/LineItem/1",
                    "title": "T-shirt",
                    "quantity": 2,
                    "variant": None,
                    "product": None,
                    "originalUnitPriceSet": _money("10.00"),
                    "discountAllocations": [],
                }
            }
        ]
        refunds = [
            _refund_node(
                refund_line_items=[
                    _refund_line_item(
                        "gid://shopify/RefundLineItem/1",
                        "gid://shopify/LineItem/1",
                        quantity=quantity,
                        amount=amount,
                    )
                ],
                return_id=return_id,
            )
        ]
        return _order_data(total_price="20.00", line_items=line_items, refunds=refunds)

    def test_creates_refund_as_return_with_source(self):
        self._run([self._order_with_refund(amount="10.00")])

        order = Order.objects.get(store=self.store)
        self.assertEqual(order.returns.count(), 1)
        order_return = order.returns.first()
        self.assertEqual(order_return.external_id, "gid://shopify/Refund/1")
        self.assertEqual(order_return.source, Return.Source.REFUND)
        self.assertEqual(order_return.status, "COMPLETED")
        self.assertEqual(order_return.amount, Decimal("10.00"))

    def test_creates_refund_line_item_linked_to_order_line_item(self):
        self._run([self._order_with_refund(quantity=1, amount="10.00")])

        refund_line_item = ReturnLineItem.objects.get(external_id="gid://shopify/RefundLineItem/1")
        self.assertEqual(refund_line_item.quantity, 1)
        self.assertEqual(refund_line_item.amount, Decimal("10.00"))
        self.assertEqual(refund_line_item.order_line_item.external_id, "gid://shopify/LineItem/1")
        self.assertEqual(refund_line_item.title, "T-shirt")

    def test_refund_amount_sums_line_items(self):
        refunds = [
            _refund_node(
                refund_line_items=[
                    _refund_line_item("gid://shopify/RefundLineItem/1", "gid://shopify/LineItem/1", amount="4.00"),
                    _refund_line_item("gid://shopify/RefundLineItem/2", "gid://shopify/LineItem/1", amount="6.00"),
                ]
            )
        ]
        self._run([_order_data(total_price="20.00", refunds=refunds)])

        order_return = Return.objects.get(external_id="gid://shopify/Refund/1")
        self.assertEqual(order_return.amount, Decimal("10.00"))

    def test_refund_line_item_null_when_line_item_missing(self):
        refunds = [
            _refund_node(
                refund_line_items=[
                    _refund_line_item("gid://shopify/RefundLineItem/1", "gid://shopify/LineItem/999", amount="10.00")
                ]
            )
        ]
        self._run([_order_data(total_price="20.00", refunds=refunds)])

        refund_line_item = ReturnLineItem.objects.get(external_id="gid://shopify/RefundLineItem/1")
        self.assertIsNone(refund_line_item.order_line_item)

    def test_refund_import_is_idempotent(self):
        order_data = self._order_with_refund(amount="10.00")
        self._run([order_data])
        self._run([order_data])

        self.assertEqual(Return.objects.filter(external_id="gid://shopify/Refund/1").count(), 1)
        self.assertEqual(ReturnLineItem.objects.filter(external_id="gid://shopify/RefundLineItem/1").count(), 1)

    def test_refund_updates_order_financials(self):
        self._run([self._order_with_refund(quantity=1, amount="10.00")])

        order = Order.objects.get(store=self.store)
        self.assertEqual(order.total_returns, Decimal("10.00"))
        self.assertEqual(order.net_revenue, Decimal("10.00"))

    def test_refund_linked_to_return_is_not_double_counted(self):
        """A refund settling a formal Return must not also be imported as its own row."""
        order_data = self._order_with_refund(amount="10.00", return_id="gid://shopify/Return/1")

        self._run([order_data])

        self.assertFalse(Return.objects.filter(external_id="gid://shopify/Refund/1").exists())
        self.assertFalse(ReturnLineItem.objects.filter(external_id="gid://shopify/RefundLineItem/1").exists())

    def test_refund_linked_to_return_does_not_inflate_total_returns(self):
        line_items = [
            {
                "node": {
                    "id": "gid://shopify/LineItem/1",
                    "title": "T-shirt",
                    "quantity": 2,
                    "variant": None,
                    "product": None,
                    "originalUnitPriceSet": _money("10.00"),
                    "discountAllocations": [],
                }
            }
        ]
        returns = [
            _return_node(
                return_line_items=[
                    _return_line_item(
                        "gid://shopify/ReturnLineItem/1", "gid://shopify/LineItem/1", quantity=1, amount="10.00"
                    )
                ]
            )
        ]
        refunds = [
            _refund_node(
                refund_line_items=[
                    _refund_line_item(
                        "gid://shopify/RefundLineItem/1",
                        "gid://shopify/LineItem/1",
                        quantity=1,
                        amount="10.00",
                    )
                ],
                return_id="gid://shopify/Return/1",
            )
        ]
        order_data = _order_data(total_price="20.00", line_items=line_items, returns=returns, refunds=refunds)

        self._run([order_data])

        order = Order.objects.get(store=self.store)
        self.assertEqual(order.returns.count(), 1)
        self.assertEqual(order.total_returns, Decimal("10.00"))
