import datetime
from decimal import Decimal

from django.test import TestCase

from core.models import CashTransaction, Store


class UpdateStoreCashAmountSignalTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
        )

    def _create_transaction(self, amount, title="Cash entry"):
        return CashTransaction.objects.create(
            store=self.store,
            title=title,
            date=datetime.date(2024, 3, 15),
            amount=Decimal(str(amount)),
            source=CashTransaction.Source.ORDER,
        )

    def test_increments_store_cash_amount_on_create(self):
        self._create_transaction("50.00")

        self.store.refresh_from_db()
        self.assertEqual(self.store.cash_amount, Decimal("50.00"))

    def test_accumulates_multiple_transactions(self):
        self._create_transaction("30.00")
        self._create_transaction("20.00")

        self.store.refresh_from_db()
        self.assertEqual(self.store.cash_amount, Decimal("50.00"))

    def test_does_not_update_on_save(self):
        txn = self._create_transaction("50.00")
        self.store.refresh_from_db()
        self.assertEqual(self.store.cash_amount, Decimal("50.00"))

        txn.amount = Decimal("100.00")
        txn.save()

        self.store.refresh_from_db()
        self.assertEqual(self.store.cash_amount, Decimal("50.00"))
