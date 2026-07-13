import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils.timezone import make_aware

from core.models import BankTransaction, CashTransaction, Order, OrderExpense, Return, Store


class OrderSignalTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
        )

    def _create_order(self, cash_paid_amount=Decimal("0"), shopify_transfer_amount=Decimal("0"), name="#1001"):
        return Order.objects.create(
            store=self.store,
            external_id="gid://shopify/Order/1",
            name=name,
            processed_at=make_aware(datetime.datetime(2024, 3, 15, 10, 0, 0)),
            cash_paid_amount=cash_paid_amount,
            shopify_transfer_amount=shopify_transfer_amount,
        )

    # --- CashTransaction ---

    def test_creates_cash_transaction_when_cash_paid(self):
        self._create_order(cash_paid_amount=Decimal("20.00"))

        self.assertEqual(CashTransaction.objects.count(), 1)
        txn = CashTransaction.objects.first()
        self.assertEqual(txn.amount, Decimal("20.00"))
        self.assertEqual(txn.source, CashTransaction.Source.ORDER)

    def test_cash_transaction_title_contains_order_name(self):
        self._create_order(cash_paid_amount=Decimal("20.00"), name="#1001")

        txn = CashTransaction.objects.first()
        self.assertIn("#1001", txn.title)

    def test_cash_transaction_date_matches_processed_at(self):
        order = Order.objects.create(
            store=self.store,
            external_id="gid://shopify/Order/2",
            name="#1002",
            processed_at=make_aware(datetime.datetime(2024, 6, 10, 14, 30, 0)),
            cash_paid_amount=Decimal("15.00"),
        )

        txn = CashTransaction.objects.get(order=order)
        self.assertEqual(txn.date, datetime.date(2024, 6, 10))

    def test_no_cash_transaction_when_cash_paid_is_zero(self):
        self._create_order(cash_paid_amount=Decimal("0"))

        self.assertEqual(CashTransaction.objects.count(), 0)

    def test_no_duplicate_cash_transaction_on_order_resave(self):
        order = self._create_order(cash_paid_amount=Decimal("20.00"))
        order.name = "#1001-updated"
        order.save()

        self.assertEqual(CashTransaction.objects.count(), 1)

    def test_cash_transaction_linked_to_order_and_store(self):
        order = self._create_order(cash_paid_amount=Decimal("10.00"))

        txn = CashTransaction.objects.first()
        self.assertEqual(txn.order, order)
        self.assertEqual(txn.store, self.store)

    # --- BankTransaction ---

    def test_creates_bank_transaction_when_shopify_transfer(self):
        self._create_order(shopify_transfer_amount=Decimal("27.50"))

        self.assertEqual(BankTransaction.objects.count(), 1)
        txn = BankTransaction.objects.first()
        self.assertEqual(txn.amount, Decimal("27.50"))
        self.assertEqual(txn.source, BankTransaction.Source.ORDER)

    def test_bank_transaction_title_contains_order_name(self):
        self._create_order(shopify_transfer_amount=Decimal("27.50"), name="#1001")

        txn = BankTransaction.objects.first()
        self.assertIn("#1001", txn.title)

    def test_bank_transaction_date_matches_processed_at(self):
        order = Order.objects.create(
            store=self.store,
            external_id="gid://shopify/Order/2",
            name="#1002",
            processed_at=make_aware(datetime.datetime(2024, 6, 10, 14, 30, 0)),
            shopify_transfer_amount=Decimal("50.00"),
        )

        txn = BankTransaction.objects.get(order=order)
        self.assertEqual(txn.date, datetime.date(2024, 6, 10))

    def test_no_bank_transaction_when_transfer_is_zero(self):
        self._create_order(shopify_transfer_amount=Decimal("0"))

        self.assertEqual(BankTransaction.objects.count(), 0)

    def test_no_duplicate_bank_transaction_on_order_resave(self):
        order = self._create_order(shopify_transfer_amount=Decimal("27.50"))
        order.name = "#1001-updated"
        order.save()

        self.assertEqual(BankTransaction.objects.count(), 1)

    def test_bank_transaction_linked_to_order_and_store(self):
        order = self._create_order(shopify_transfer_amount=Decimal("27.50"))

        txn = BankTransaction.objects.first()
        self.assertEqual(txn.order, order)
        self.assertEqual(txn.store, self.store)

    # --- BankTransaction for OrderExpense (delivery) ---

    def test_creates_bank_transaction_when_delivery_expense_added(self):
        order = self._create_order()
        OrderExpense.objects.create(
            order=order,
            type=OrderExpense.Type.DELIVERY,
            source=OrderExpense.Source.MANUAL,
            amount=Decimal("5.00"),
        )

        self.assertEqual(BankTransaction.objects.count(), 1)
        txn = BankTransaction.objects.first()
        self.assertEqual(txn.source, BankTransaction.Source.ORDER_DELIVERY)
        self.assertEqual(txn.amount, Decimal("-5.00"))
        self.assertEqual(txn.store, self.store)
        self.assertIn(order.name, txn.title)
        self.assertEqual(txn.date, order.processed_at.date())

    def test_no_bank_transaction_when_non_delivery_expense_added(self):
        order = self._create_order()
        OrderExpense.objects.create(
            order=order,
            type=OrderExpense.Type.PACKAGING,
            source=OrderExpense.Source.MANUAL,
            amount=Decimal("2.00"),
        )

        self.assertFalse(BankTransaction.objects.filter(source=BankTransaction.Source.ORDER_DELIVERY).exists())

    # --- BankTransaction for Return ---

    def _create_return(self, order, amount=Decimal("50.00"), name="#1001-R1"):
        return Return.objects.create(
            order=order,
            external_id="gid://shopify/Return/1",
            name=name,
            status="CLOSED",
            amount=amount,
        )

    def test_creates_bank_transaction_when_return_created(self):
        order = self._create_order()
        self._create_return(order, amount=Decimal("50.00"))

        txn = BankTransaction.objects.get(source=BankTransaction.Source.RETURN)
        self.assertEqual(txn.amount, Decimal("-50.00"))
        self.assertEqual(txn.store, self.store)
        self.assertEqual(txn.date, order.processed_at.date())

    def test_return_bank_transaction_title_contains_return_name(self):
        order = self._create_order()
        self._create_return(order, name="#1001-R1")

        txn = BankTransaction.objects.get(source=BankTransaction.Source.RETURN)
        self.assertIn("#1001-R1", txn.title)

    def test_no_bank_transaction_when_return_amount_zero(self):
        order = self._create_order()
        self._create_return(order, amount=Decimal("0"))

        self.assertFalse(BankTransaction.objects.filter(source=BankTransaction.Source.RETURN).exists())

    def test_no_duplicate_return_bank_transaction_on_resave(self):
        order = self._create_order()
        order_return = self._create_return(order, amount=Decimal("50.00"))
        order_return.status = "OPEN"
        order_return.save()

        self.assertEqual(BankTransaction.objects.filter(source=BankTransaction.Source.RETURN).count(), 1)
