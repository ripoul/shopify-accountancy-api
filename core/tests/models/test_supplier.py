from django.test import TestCase

from core.models import Store, Supplier


class SupplierModelTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="my-shop.myshopify.com",
            name="My Shop",
            access_token="shpat_token",
        )
        self.supplier = Supplier.objects.create(store=self.store, name="Acme")

    def test_str_returns_name(self):
        self.assertEqual(str(self.supplier), "Acme")
