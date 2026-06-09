from django.db import IntegrityError
from django.test import TestCase

from core.models import Store


class StoreModelTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="my-shop.myshopify.com",
            name="My Shop",
            access_token="shpat_token",
            scopes="read_orders",
        )

    def test_str_returns_shop_domain(self):
        self.assertEqual(str(self.store), "my-shop.myshopify.com")

    def test_shop_domain_is_unique(self):
        with self.assertRaises(IntegrityError):
            Store.objects.create(
                shop_domain="my-shop.myshopify.com",
                name="Duplicate",
                access_token="shpat_other",
            )

    def test_scopes_can_be_blank(self):
        store = Store.objects.create(
            shop_domain="blank-scopes.myshopify.com",
            name="No Scopes",
            access_token="shpat_token2",
        )
        self.assertEqual(store.scopes, "")

    def test_created_at_and_updated_at_are_set(self):
        self.assertIsNotNone(self.store.created_at)
        self.assertIsNotNone(self.store.updated_at)
