import datetime
from decimal import Decimal

from django.test import TestCase

from core.models import BankTransaction, Store


class UpdateStoreBankAmountSignalTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
        )

    def _create_transaction(self, amount, title="Bank entry"):
        return BankTransaction.objects.create(
            store=self.store,
            title=title,
            date=datetime.date(2024, 3, 15),
            amount=Decimal(str(amount)),
            source=BankTransaction.Source.OTHER,
        )

    def test_increments_store_bank_amount_on_create(self):
        self._create_transaction("100.00")

        self.store.refresh_from_db()
        self.assertEqual(self.store.bank_amount, Decimal("100.00"))

    def test_accumulates_multiple_transactions(self):
        self._create_transaction("60.00")
        self._create_transaction("40.00")

        self.store.refresh_from_db()
        self.assertEqual(self.store.bank_amount, Decimal("100.00"))

    def test_updates_bank_amount_on_save(self):
        txn = self._create_transaction("100.00")
        self.store.refresh_from_db()
        self.assertEqual(self.store.bank_amount, Decimal("100.00"))

        txn.amount = Decimal("200.00")
        txn.save()

        self.store.refresh_from_db()
        self.assertEqual(self.store.bank_amount, Decimal("200.00"))

    def test_recounts_bank_amount_on_delete(self):
        txn = self._create_transaction("100.00")
        self.store.refresh_from_db()
        self.assertEqual(self.store.bank_amount, Decimal("100.00"))

        txn.delete()

        self.store.refresh_from_db()
        self.assertEqual(self.store.bank_amount, Decimal("0.00"))
