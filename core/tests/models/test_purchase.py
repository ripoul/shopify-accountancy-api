from datetime import date

from django.test import TestCase

from core.models import Purchase, Store, Supplier


class PurchaseModelTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="my-shop.myshopify.com",
            name="My Shop",
            access_token="shpat_token",
        )
        self.supplier = Supplier.objects.create(store=self.store, name="Acme")
        self.purchase = Purchase.objects.create(
            store=self.store,
            supplier=self.supplier,
            order_date=date(2026, 1, 15),
            price="120.50",
        )

    def test_str_returns_supplier_and_order_date(self):
        self.assertEqual(str(self.purchase), "Acme - 2026-01-15")

    def test_boolean_defaults_are_false(self):
        self.assertFalse(self.purchase.is_raw_material)
        self.assertFalse(self.purchase.reception_checked)
        self.assertFalse(self.purchase.has_supporting_documents)

    def test_order_number_defaults_to_blank(self):
        self.assertEqual(self.purchase.order_number, "")

    def test_nullable_fields_default_to_none(self):
        self.assertIsNone(self.purchase.reception_date)
        self.assertIsNone(self.purchase.claim_text)
        self.assertIsNone(self.purchase.claim_date)
        self.assertIsNone(self.purchase.supplier_return_text)
        self.assertIsNone(self.purchase.claim_closed_at)
