import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils.timezone import make_aware

from core.models import BankTransaction, Order, Purchase, Royalty, Store, Supplier, Tax


class RoyaltySignalFromOrderTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
            royalty_rate=Decimal("10"),
        )

    def _create_order(self, after_tax_result, processed_at, external_id="gid://shopify/Order/1"):
        return Order.objects.create(
            store=self.store,
            external_id=external_id,
            name="#1001",
            processed_at=make_aware(processed_at),
            after_tax_result=after_tax_result,
            quarter="2024/01",
        )

    def test_creates_royalty_when_order_with_quarter_saved(self):
        self._create_order(Decimal("100.00"), datetime.datetime(2024, 3, 15, 10, 0, 0))
        self.assertEqual(Royalty.objects.count(), 1)
        royalty = Royalty.objects.first()
        self.assertEqual(royalty.quarter, "2024/01")
        self.assertEqual(royalty.store, self.store)

    def test_amount_is_rate_percent_of_after_tax_result(self):
        self._create_order(Decimal("100.00"), datetime.datetime(2024, 3, 15, 10, 0, 0))
        royalty = Royalty.objects.get(store=self.store, quarter="2024/01")
        self.assertEqual(royalty.amount, Decimal("10.00"))  # 100 * 10%

    def test_breakdown_columns_stored(self):
        self._create_order(Decimal("100.00"), datetime.datetime(2024, 3, 15, 10, 0, 0))
        royalty = Royalty.objects.get(store=self.store, quarter="2024/01")
        self.assertEqual(royalty.sum_after_tax_result, Decimal("100.00"))
        self.assertEqual(royalty.sum_purchase_price, Decimal("0.00"))

    def test_amount_aggregates_all_orders_in_quarter(self):
        self._create_order(Decimal("100.00"), datetime.datetime(2024, 3, 1, 10, 0, 0), external_id="id-1")
        self._create_order(Decimal("200.00"), datetime.datetime(2024, 3, 2, 10, 0, 0), external_id="id-2")
        royalty = Royalty.objects.get(store=self.store, quarter="2024/01")
        self.assertEqual(royalty.amount, Decimal("30.00"))  # 300 * 10%
        self.assertEqual(royalty.sum_after_tax_result, Decimal("300.00"))

    def test_amount_is_zero_when_after_tax_result_is_negative(self):
        self._create_order(Decimal("-50.00"), datetime.datetime(2024, 3, 15, 10, 0, 0))
        royalty = Royalty.objects.get(store=self.store, quarter="2024/01")
        self.assertEqual(royalty.amount, Decimal("0.00"))
        self.assertEqual(royalty.sum_after_tax_result, Decimal("-50.00"))  # stored as-is

    def test_recalculates_on_order_update(self):
        order = self._create_order(Decimal("100.00"), datetime.datetime(2024, 3, 15, 10, 0, 0))
        order.after_tax_result = Decimal("200.00")
        order.save()
        royalty = Royalty.objects.get(store=self.store, quarter="2024/01")
        self.assertEqual(royalty.amount, Decimal("20.00"))  # 200 * 10%

    def test_does_not_recalculate_if_royalty_already_paid(self):
        order = self._create_order(Decimal("100.00"), datetime.datetime(2024, 3, 15, 10, 0, 0))
        royalty = Royalty.objects.get(store=self.store, quarter="2024/01")
        royalty.payment_date = datetime.date(2024, 4, 30)
        royalty.save()
        frozen_amount = royalty.amount

        order.after_tax_result = Decimal("999.00")
        order.save()

        royalty.refresh_from_db()
        self.assertEqual(royalty.amount, frozen_amount)

    def test_skips_when_quarter_is_empty(self):
        Order.objects.create(
            store=self.store,
            external_id="gid://shopify/Order/9",
            name="#1009",
            processed_at=make_aware(datetime.datetime(2024, 3, 15, 10, 0, 0)),
            after_tax_result=Decimal("100.00"),
            quarter="",
        )
        self.assertEqual(Royalty.objects.count(), 0)

    def test_separate_quarters_have_separate_royalty_records(self):
        for quarter, month, eid in [("2024/01", 3, "id-1"), ("2024/02", 6, "id-2")]:
            Order.objects.create(
                store=self.store,
                external_id=eid,
                name=f"#{eid}",
                processed_at=make_aware(datetime.datetime(2024, month, 1, 10, 0, 0)),
                after_tax_result=Decimal("100.00"),
                quarter=quarter,
            )
        self.assertEqual(Royalty.objects.count(), 2)

    def test_does_not_mix_stores(self):
        other_store = Store.objects.create(
            shop_domain="other.myshopify.com",
            name="Other",
            access_token="shpat_other",
            royalty_rate=Decimal("10"),
        )
        Order.objects.create(
            store=other_store,
            external_id="id-other",
            name="#2001",
            processed_at=make_aware(datetime.datetime(2024, 3, 15, 10, 0, 0)),
            after_tax_result=Decimal("500.00"),
            quarter="2024/01",
        )
        self._create_order(Decimal("100.00"), datetime.datetime(2024, 3, 1, 10, 0, 0))

        royalty = Royalty.objects.get(store=self.store, quarter="2024/01")
        self.assertEqual(royalty.amount, Decimal("10.00"))  # only 100 * 10%

    def test_zero_rate_produces_zero_amount(self):
        self.store.royalty_rate = Decimal("0")
        self.store.save()
        self._create_order(Decimal("500.00"), datetime.datetime(2024, 3, 15, 10, 0, 0))
        royalty = Royalty.objects.get(store=self.store, quarter="2024/01")
        self.assertEqual(royalty.amount, Decimal("0.00"))


class RoyaltyPaymentSignalTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
        )
        self.royalty = Royalty.objects.create(
            store=self.store,
            quarter="2024/01",
            amount=Decimal("50.00"),
        )

    def test_creates_bank_transaction_when_payment_date_set(self):
        self.royalty.payment_date = datetime.date(2024, 4, 30)
        self.royalty.save()

        self.assertEqual(BankTransaction.objects.count(), 1)
        bt = BankTransaction.objects.first()
        self.assertEqual(bt.amount, Decimal("-50.00"))
        self.assertEqual(bt.source, BankTransaction.Source.ROYALTY)
        self.assertEqual(bt.date, datetime.date(2024, 4, 30))
        self.assertEqual(bt.store, self.store)

    def test_bank_transaction_title_contains_quarter(self):
        self.royalty.payment_date = datetime.date(2024, 4, 30)
        self.royalty.save()

        bt = BankTransaction.objects.first()
        self.assertIn("2024/01", bt.title)

    def test_bank_transaction_linked_on_royalty(self):
        self.royalty.payment_date = datetime.date(2024, 4, 30)
        self.royalty.save()

        self.royalty.refresh_from_db()
        self.assertIsNotNone(self.royalty.bank_transaction)

    def test_no_duplicate_bank_transaction_on_resave(self):
        self.royalty.payment_date = datetime.date(2024, 4, 30)
        self.royalty.save()
        self.royalty.save()

        self.assertEqual(BankTransaction.objects.count(), 1)

    def test_no_bank_transaction_without_payment_date(self):
        self.royalty.save()
        self.assertEqual(BankTransaction.objects.count(), 0)


class StoreRoyaltyRateChangeSignalTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
            royalty_rate=Decimal("10"),
        )
        Royalty.objects.create(store=self.store, quarter="2024/01", amount=Decimal("10.00"))
        Royalty.objects.create(store=self.store, quarter="2024/02", amount=Decimal("5.00"))

    def test_recalculates_all_unlocked_royalties_when_rate_changes(self):
        from django.utils.timezone import make_aware

        Order.objects.create(
            store=self.store,
            external_id="id-q1",
            name="#Q1",
            processed_at=make_aware(datetime.datetime(2024, 3, 1, 10, 0, 0)),
            after_tax_result=Decimal("100.00"),
            quarter="2024/01",
        )
        Order.objects.create(
            store=self.store,
            external_id="id-q2",
            name="#Q2",
            processed_at=make_aware(datetime.datetime(2024, 6, 1, 10, 0, 0)),
            after_tax_result=Decimal("50.00"),
            quarter="2024/02",
        )

        self.store.royalty_rate = Decimal("20")
        self.store.save()

        r1 = Royalty.objects.get(store=self.store, quarter="2024/01")
        r2 = Royalty.objects.get(store=self.store, quarter="2024/02")
        self.assertEqual(r1.amount, Decimal("20.00"))  # 100 * 20% (recalculated by order signal on creation)
        self.assertEqual(r2.amount, Decimal("10.00"))  # 50 * 20%

    def test_does_not_recalculate_locked_royalties(self):
        from django.utils.timezone import make_aware

        Order.objects.create(
            store=self.store,
            external_id="id-q1",
            name="#Q1",
            processed_at=make_aware(datetime.datetime(2024, 3, 1, 10, 0, 0)),
            after_tax_result=Decimal("100.00"),
            quarter="2024/01",
        )

        r1 = Royalty.objects.get(store=self.store, quarter="2024/01")
        r1.payment_date = datetime.date(2024, 4, 30)
        r1.save()
        frozen_amount = r1.amount

        self.store.royalty_rate = Decimal("50")
        self.store.save()

        r1.refresh_from_db()
        self.assertEqual(r1.amount, frozen_amount)

    def test_no_recalculation_when_rate_unchanged(self):
        Royalty.objects.filter(store=self.store).update(amount=Decimal("999.00"))
        self.store.royalty_rate = Decimal("10")
        self.store.save()

        amounts = list(Royalty.objects.filter(store=self.store).values_list("amount", flat=True))
        self.assertIn(Decimal("999.00"), amounts)


class RoyaltyPurchaseDeductionTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
            royalty_rate=Decimal("10"),
        )
        self.supplier = Supplier.objects.create(store=self.store, name="Acme")

    def _create_order(self, after_tax_result, external_id="id-1"):
        return Order.objects.create(
            store=self.store,
            external_id=external_id,
            name=f"#{external_id}",
            processed_at=make_aware(datetime.datetime(2024, 3, 15, 10, 0, 0)),
            after_tax_result=after_tax_result,
            quarter="2024/01",
        )

    def _create_purchase(self, price, order_date=datetime.date(2024, 2, 10)):
        return Purchase.objects.create(
            store=self.store,
            supplier=self.supplier,
            order_date=order_date,
            price=Decimal(str(price)),
        )

    def test_purchase_is_deducted_from_royalty_base(self):
        self._create_order(Decimal("200.00"))
        self._create_purchase(price="50.00")  # Q1 purchase → deducted
        royalty = Royalty.objects.get(store=self.store, quarter="2024/01")
        self.assertEqual(royalty.amount, Decimal("15.00"))  # (200 - 50) * 10%
        self.assertEqual(royalty.sum_after_tax_result, Decimal("200.00"))
        self.assertEqual(royalty.sum_purchase_price, Decimal("50.00"))

    def test_purchase_in_other_quarter_not_deducted(self):
        self._create_order(Decimal("200.00"))
        self._create_purchase(price="50.00", order_date=datetime.date(2024, 4, 1))  # Q2 → not deducted
        royalty = Royalty.objects.get(store=self.store, quarter="2024/01")
        self.assertEqual(royalty.amount, Decimal("20.00"))  # 200 * 10%

    def test_result_clamped_to_zero_when_purchases_exceed_revenue(self):
        self._create_order(Decimal("100.00"))
        self._create_purchase(price="200.00")  # exceeds after_tax_result
        royalty = Royalty.objects.get(store=self.store, quarter="2024/01")
        self.assertEqual(royalty.amount, Decimal("0.00"))

    def test_royalty_recalculates_when_purchase_added(self):
        self._create_order(Decimal("200.00"))
        royalty = Royalty.objects.get(store=self.store, quarter="2024/01")
        self.assertEqual(royalty.amount, Decimal("20.00"))  # 200 * 10% before purchase

        self._create_purchase(price="100.00")
        royalty.refresh_from_db()
        self.assertEqual(royalty.amount, Decimal("10.00"))  # (200 - 100) * 10%

    def test_royalty_recalculates_when_purchase_deleted(self):
        self._create_order(Decimal("200.00"))
        purchase = self._create_purchase(price="100.00")
        royalty = Royalty.objects.get(store=self.store, quarter="2024/01")
        self.assertEqual(royalty.amount, Decimal("10.00"))  # (200 - 100) * 10%

        purchase.delete()
        royalty.refresh_from_db()
        self.assertEqual(royalty.amount, Decimal("20.00"))  # 200 * 10% again

    def test_locked_royalty_not_recalculated_on_purchase(self):
        self._create_order(Decimal("200.00"))
        royalty = Royalty.objects.get(store=self.store, quarter="2024/01")
        royalty.payment_date = datetime.date(2024, 4, 30)
        royalty.save()
        frozen_amount = royalty.amount

        self._create_purchase(price="100.00")
        royalty.refresh_from_db()
        self.assertEqual(royalty.amount, frozen_amount)


class RoyaltyTaxTriggerTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
            royalty_rate=Decimal("10"),
        )

    def test_royalty_recalculates_when_tax_saved(self):
        Order.objects.create(
            store=self.store,
            external_id="id-1",
            name="#1",
            processed_at=make_aware(datetime.datetime(2024, 3, 15, 10, 0, 0)),
            after_tax_result=Decimal("300.00"),
            quarter="2024/01",
        )
        royalty = Royalty.objects.get(store=self.store, quarter="2024/01")
        Royalty.objects.filter(pk=royalty.pk).update(amount=Decimal("999.00"))

        tax, _ = Tax.objects.update_or_create(
            store=self.store, quarter="2024/01", defaults={"amount": Decimal("40.20")}
        )

        royalty.refresh_from_db()
        self.assertEqual(royalty.amount, Decimal("30.00"))  # 300 * 10%

    def test_locked_royalty_not_recalculated_on_tax_save(self):
        Order.objects.create(
            store=self.store,
            external_id="id-1",
            name="#1",
            processed_at=make_aware(datetime.datetime(2024, 3, 15, 10, 0, 0)),
            after_tax_result=Decimal("300.00"),
            quarter="2024/01",
        )
        royalty = Royalty.objects.get(store=self.store, quarter="2024/01")
        royalty.payment_date = datetime.date(2024, 4, 30)
        royalty.save()
        frozen_amount = royalty.amount

        tax, _ = Tax.objects.update_or_create(
            store=self.store, quarter="2024/01", defaults={"amount": Decimal("40.20")}
        )

        royalty.refresh_from_db()
        self.assertEqual(royalty.amount, frozen_amount)
