import datetime
from decimal import Decimal

from django.test import TestCase

from core.models import BankTransaction, Purchase, Store, Supplier


class CreateBankTransactionForPurchaseTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
        )
        self.supplier = Supplier.objects.create(store=self.store, name="Acme Corp")

    def _create_purchase(self, price="150.00", order_date=datetime.date(2024, 3, 15)):
        return Purchase.objects.create(
            store=self.store,
            supplier=self.supplier,
            order_date=order_date,
            price=Decimal(price),
        )

    def test_creates_bank_transaction_on_purchase_create(self):
        self._create_purchase()

        self.assertEqual(BankTransaction.objects.count(), 1)

    def test_bank_transaction_amount_is_negative_price(self):
        self._create_purchase(price="150.00")

        txn = BankTransaction.objects.first()
        self.assertEqual(txn.amount, Decimal("-150.00"))

    def test_bank_transaction_title_contains_supplier_and_price(self):
        self._create_purchase(price="150.00")

        txn = BankTransaction.objects.first()
        self.assertIn("Acme Corp", txn.title)
        self.assertIn("150.00", txn.title)

    def test_bank_transaction_date_matches_order_date(self):
        self._create_purchase(order_date=datetime.date(2024, 6, 10))

        txn = BankTransaction.objects.first()
        self.assertEqual(txn.date, datetime.date(2024, 6, 10))

    def test_bank_transaction_source_is_purchase(self):
        self._create_purchase()

        txn = BankTransaction.objects.first()
        self.assertEqual(txn.source, BankTransaction.Source.PURCHASE)

    def test_bank_transaction_store_matches_purchase_store(self):
        self._create_purchase()

        txn = BankTransaction.objects.first()
        self.assertEqual(txn.store, self.store)

    def test_no_duplicate_bank_transaction_on_purchase_resave(self):
        purchase = self._create_purchase()
        purchase.order_number = "CMD-001"
        purchase.save()

        self.assertEqual(BankTransaction.objects.count(), 1)
