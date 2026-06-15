import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils.timezone import make_aware

from core.models import BankTransaction, Order, Store, Tax


class TaxSignalFromOrderTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
        )

    def _create_order(self, total_price, processed_at, external_id="gid://shopify/Order/1"):
        return Order.objects.create(
            store=self.store,
            external_id=external_id,
            name="#1001",
            processed_at=make_aware(processed_at),
            total_price=total_price,
            quarter="",
        )

    def test_creates_tax_when_order_with_quarter_saved(self):
        order = self._create_order(Decimal("100.00"), datetime.datetime(2024, 3, 15, 10, 0, 0))
        order.quarter = "2024/01"
        order.save()

        self.assertEqual(Tax.objects.count(), 1)
        tax = Tax.objects.first()
        self.assertEqual(tax.quarter, "2024/01")
        self.assertEqual(tax.store, self.store)

    def test_amount_is_134_percent_of_total_price(self):
        order = self._create_order(Decimal("100.00"), datetime.datetime(2024, 3, 15, 10, 0, 0))
        order.quarter = "2024/01"
        order.save()

        tax = Tax.objects.get(store=self.store, quarter="2024/01")
        self.assertEqual(tax.amount, Decimal("13.40"))

    def test_amount_aggregates_all_orders_in_quarter(self):
        for i, price in enumerate([Decimal("100.00"), Decimal("200.00")], start=1):
            order = self._create_order(price, datetime.datetime(2024, 3, i, 10, 0, 0), external_id=f"id-{i}")
            order.quarter = "2024/01"
            order.save()

        tax = Tax.objects.get(store=self.store, quarter="2024/01")
        self.assertEqual(tax.amount, Decimal("40.20"))  # 300 * 0.134

    def test_recalculates_on_order_update(self):
        order = self._create_order(Decimal("100.00"), datetime.datetime(2024, 3, 15, 10, 0, 0))
        order.quarter = "2024/01"
        order.save()

        order.total_price = Decimal("200.00")
        order.save()

        tax = Tax.objects.get(store=self.store, quarter="2024/01")
        self.assertEqual(tax.amount, Decimal("26.80"))

    def test_does_not_recalculate_if_tax_already_paid(self):
        order = self._create_order(Decimal("100.00"), datetime.datetime(2024, 3, 15, 10, 0, 0))
        order.quarter = "2024/01"
        order.save()

        tax = Tax.objects.get(store=self.store, quarter="2024/01")
        tax.payment_date = datetime.date(2024, 4, 30)
        tax.save()
        frozen_amount = tax.amount

        order.total_price = Decimal("999.00")
        order.save()

        tax.refresh_from_db()
        self.assertEqual(tax.amount, frozen_amount)

    def test_skips_when_quarter_is_empty(self):
        Order.objects.create(
            store=self.store,
            external_id="gid://shopify/Order/9",
            name="#1009",
            processed_at=make_aware(datetime.datetime(2024, 3, 15, 10, 0, 0)),
            total_price=Decimal("100.00"),
            quarter="",
        )
        self.assertEqual(Tax.objects.count(), 0)

    def test_separate_quarters_have_separate_tax_records(self):
        for quarter, month, eid in [("2024/01", 3, "id-1"), ("2024/02", 6, "id-2")]:
            order = self._create_order(Decimal("100.00"), datetime.datetime(2024, month, 1, 10, 0, 0), eid)
            order.quarter = quarter
            order.save()

        self.assertEqual(Tax.objects.count(), 2)

    def test_does_not_mix_stores(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        Order.objects.create(
            store=other_store,
            external_id="id-other",
            name="#2001",
            processed_at=make_aware(datetime.datetime(2024, 3, 15, 10, 0, 0)),
            total_price=Decimal("500.00"),
            quarter="2024/01",
        )
        order = self._create_order(Decimal("100.00"), datetime.datetime(2024, 3, 1, 10, 0, 0))
        order.quarter = "2024/01"
        order.save()

        tax = Tax.objects.get(store=self.store, quarter="2024/01")
        self.assertEqual(tax.amount, Decimal("13.40"))


class TaxPaymentSignalTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
        )
        self.tax = Tax.objects.create(
            store=self.store,
            quarter="2024/01",
            amount=Decimal("134.00"),
        )

    def test_creates_bank_transaction_when_payment_date_set(self):
        self.tax.payment_date = datetime.date(2024, 4, 30)
        self.tax.save()

        self.assertEqual(BankTransaction.objects.count(), 1)
        bt = BankTransaction.objects.first()
        self.assertEqual(bt.amount, Decimal("-134.00"))
        self.assertEqual(bt.source, BankTransaction.Source.TAX)
        self.assertEqual(bt.date, datetime.date(2024, 4, 30))
        self.assertEqual(bt.store, self.store)

    def test_bank_transaction_title_contains_quarter(self):
        self.tax.payment_date = datetime.date(2024, 4, 30)
        self.tax.save()

        bt = BankTransaction.objects.first()
        self.assertIn("2024/01", bt.title)

    def test_bank_transaction_linked_on_tax(self):
        self.tax.payment_date = datetime.date(2024, 4, 30)
        self.tax.save()

        self.tax.refresh_from_db()
        self.assertIsNotNone(self.tax.bank_transaction)

    def test_no_duplicate_bank_transaction_on_resave(self):
        self.tax.payment_date = datetime.date(2024, 4, 30)
        self.tax.save()
        self.tax.save()

        self.assertEqual(BankTransaction.objects.count(), 1)

    def test_no_bank_transaction_without_payment_date(self):
        self.tax.save()
        self.assertEqual(BankTransaction.objects.count(), 0)
