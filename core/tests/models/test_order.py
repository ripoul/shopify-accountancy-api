import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils.timezone import make_aware

from core.models import Order, OrderExpense, OrderLineItem, Product, ProductVariant, Return, ReturnLineItem, Store


class OrderModelTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
        )
        self.product = Product.objects.create(
            store=self.store,
            external_id="gid://shopify/Product/1",
            title="T-shirt",
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            external_id="gid://shopify/ProductVariant/1",
            title="M",
            price="29.99",
            distributor_price=Decimal("12.00"),
        )

    def _create_order(self, total_price="100.00", processed_at=None):
        return Order.objects.create(
            store=self.store,
            external_id="gid://shopify/Order/1",
            name="#1001",
            processed_at=processed_at or make_aware(datetime.datetime(2024, 3, 15, 10, 0, 0)),
            total_price=Decimal(total_price),
        )

    def test_str_returns_name(self):
        order = self._create_order()
        self.assertEqual(str(order), "#1001")

    def test_recompute_financials_purchase_cost(self):
        order = self._create_order(total_price="100.00")
        OrderLineItem.objects.create(
            order=order,
            external_id="gid://shopify/LineItem/1",
            title="T-shirt",
            quantity=2,
            unit_price=Decimal("50.00"),
            distributor_price=Decimal("12.00"),
            variant=self.variant,
        )

        order.recompute_financials()

        order.refresh_from_db()
        self.assertEqual(order.product_purchase_cost, Decimal("24.00"))  # 12.00 * 2

    def test_recompute_financials_no_distributor_price_skipped(self):
        variant_no_cost = ProductVariant.objects.create(
            product=self.product,
            external_id="gid://shopify/ProductVariant/2",
            title="L",
            price="29.99",
            distributor_price=None,
        )
        order = self._create_order(total_price="100.00")
        OrderLineItem.objects.create(
            order=order,
            external_id="gid://shopify/LineItem/1",
            title="T-shirt",
            quantity=1,
            unit_price=Decimal("100.00"),
            variant=variant_no_cost,
        )

        order.recompute_financials()

        order.refresh_from_db()
        self.assertEqual(order.product_purchase_cost, Decimal("0"))

    def test_recompute_financials_net_margin(self):
        order = self._create_order(total_price="100.00")
        OrderExpense.objects.create(
            order=order,
            type=OrderExpense.Type.SHOPIFY_PAYMENT,
            source=OrderExpense.Source.AUTO,
            amount=Decimal("3.00"),
        )
        OrderLineItem.objects.create(
            order=order,
            external_id="gid://shopify/LineItem/1",
            title="T-shirt",
            quantity=1,
            unit_price=Decimal("100.00"),
            distributor_price=Decimal("12.00"),
            variant=self.variant,
        )

        order.recompute_financials()

        order.refresh_from_db()
        # net_margin = total_price - expenses - purchase_cost = 100 - 3 - 12 = 85
        self.assertEqual(order.net_margin, Decimal("85.00"))

    def test_recompute_financials_after_tax_result(self):
        order = self._create_order(total_price="100.00")

        order.recompute_financials()

        order.refresh_from_db()
        # after_tax_result = net_margin - (total_price * 0.134) = 100 - 13.40 = 86.60
        self.assertEqual(order.after_tax_result, Decimal("86.60"))

    def test_recompute_financials_shopify_transfer_amount(self):
        order = self._create_order(total_price="100.00")
        OrderExpense.objects.create(
            order=order,
            type=OrderExpense.Type.SHOPIFY_PAYMENT,
            source=OrderExpense.Source.AUTO,
            amount=Decimal("2.50"),
        )

        order.recompute_financials()

        order.refresh_from_db()
        # shopify_transfer_amount = total_price - shopify_fee = 100 - 2.50 = 97.50
        self.assertEqual(order.shopify_transfer_amount, Decimal("97.50"))

    def test_recompute_financials_non_shopify_expense_not_in_transfer(self):
        order = self._create_order(total_price="100.00")
        OrderExpense.objects.create(
            order=order,
            type=OrderExpense.Type.DELIVERY,
            source=OrderExpense.Source.MANUAL,
            amount=Decimal("5.00"),
        )

        order.recompute_financials()

        order.refresh_from_db()
        # shopify_transfer_amount = total_price - 0 (no shopify fee) = 100
        self.assertEqual(order.shopify_transfer_amount, Decimal("100.00"))
        # but net_margin = 100 - 5 - 0 = 95
        self.assertEqual(order.net_margin, Decimal("95.00"))

    def _add_return(self, order, line_item, quantity=1, amount="50.00", source=Return.Source.RETURN):
        order_return = Return.objects.create(
            order=order,
            external_id="gid://shopify/Return/1",
            source=source,
            name="#1001-R1",
            status="CLOSED",
            amount=Decimal(amount),
        )
        ReturnLineItem.objects.create(
            return_ref=order_return,
            order_line_item=line_item,
            external_id="gid://shopify/ReturnLineItem/1",
            quantity=quantity,
            amount=Decimal(amount),
        )
        return order_return

    def test_recompute_financials_total_returns_and_net_revenue(self):
        order = self._create_order(total_price="100.00")
        line_item = OrderLineItem.objects.create(
            order=order,
            external_id="gid://shopify/LineItem/1",
            title="T-shirt",
            quantity=2,
            unit_price=Decimal("50.00"),
            distributor_price=Decimal("12.00"),
            variant=self.variant,
        )
        self._add_return(order, line_item, quantity=1, amount="50.00")

        order.recompute_financials()

        order.refresh_from_db()
        self.assertEqual(order.total_returns, Decimal("50.00"))
        self.assertEqual(order.net_revenue, Decimal("50.00"))
        self.assertEqual(order.returns_purchase_cost, Decimal("12.00"))  # 12.00 * 1

    def test_recompute_financials_net_margin_with_return_restock(self):
        order = self._create_order(total_price="100.00")
        line_item = OrderLineItem.objects.create(
            order=order,
            external_id="gid://shopify/LineItem/1",
            title="T-shirt",
            quantity=2,
            unit_price=Decimal("50.00"),
            distributor_price=Decimal("12.00"),
            variant=self.variant,
        )
        self._add_return(order, line_item, quantity=1, amount="50.00")

        order.recompute_financials()

        order.refresh_from_db()
        # purchase_cost = 24 ; net_revenue = 50 ; net_margin = 50 - (24 - 12) = 38
        self.assertEqual(order.net_margin, Decimal("38.00"))
        # after_tax_result = 38 - (50 * 0.134) = 38 - 6.70 = 31.30
        self.assertEqual(order.after_tax_result, Decimal("31.30"))

    def test_recompute_financials_treats_refund_source_same_as_return(self):
        order = self._create_order(total_price="100.00")
        line_item = OrderLineItem.objects.create(
            order=order,
            external_id="gid://shopify/LineItem/1",
            title="T-shirt",
            quantity=2,
            unit_price=Decimal("50.00"),
            distributor_price=Decimal("12.00"),
            variant=self.variant,
        )
        self._add_return(order, line_item, quantity=1, amount="50.00", source=Return.Source.REFUND)

        order.recompute_financials()

        order.refresh_from_db()
        self.assertEqual(order.total_returns, Decimal("50.00"))
        self.assertEqual(order.net_revenue, Decimal("50.00"))
        self.assertEqual(order.returns_purchase_cost, Decimal("12.00"))

    def test_recompute_financials_no_returns_defaults(self):
        order = self._create_order(total_price="100.00")

        order.recompute_financials()

        order.refresh_from_db()
        self.assertEqual(order.total_returns, Decimal("0"))
        self.assertEqual(order.returns_purchase_cost, Decimal("0"))
        self.assertEqual(order.net_revenue, Decimal("100.00"))

    def test_recompute_financials_sets_quarter(self):
        order = self._create_order(processed_at=make_aware(datetime.datetime(2024, 3, 15, 10, 0, 0)))
        order.recompute_financials()
        order.refresh_from_db()
        self.assertEqual(order.quarter, "2024/01")

    def test_compute_quarter_q1(self):
        order = self._create_order(processed_at=make_aware(datetime.datetime(2024, 1, 1)))
        order.recompute_financials()
        order.refresh_from_db()
        self.assertEqual(order.quarter, "2024/01")

    def test_compute_quarter_q2(self):
        order = self._create_order(processed_at=make_aware(datetime.datetime(2024, 4, 1)))
        order.recompute_financials()
        order.refresh_from_db()
        self.assertEqual(order.quarter, "2024/02")

    def test_compute_quarter_q3(self):
        order = self._create_order(processed_at=make_aware(datetime.datetime(2024, 7, 1)))
        order.recompute_financials()
        order.refresh_from_db()
        self.assertEqual(order.quarter, "2024/03")

    def test_compute_quarter_q4(self):
        order = self._create_order(processed_at=make_aware(datetime.datetime(2024, 10, 1)))
        order.recompute_financials()
        order.refresh_from_db()
        self.assertEqual(order.quarter, "2024/04")
