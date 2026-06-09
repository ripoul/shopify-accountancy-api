from django.db import IntegrityError
from django.test import TestCase

from core.models import Collection, Product, ProductVariant, Store


class CollectionModelTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="my-shop.myshopify.com",
            name="My Shop",
            access_token="shpat_token",
        )
        self.collection = Collection.objects.create(
            store=self.store,
            external_id="gid://shopify/Collection/1",
            title="Nouveautés",
        )

    def test_str_returns_title(self):
        self.assertEqual(str(self.collection), "Nouveautés")

    def test_unique_together_store_and_external_id(self):
        with self.assertRaises(IntegrityError):
            Collection.objects.create(
                store=self.store,
                external_id="gid://shopify/Collection/1",
                title="Duplicate",
            )

    def test_same_external_id_allowed_on_different_stores(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        collection = Collection.objects.create(
            store=other_store,
            external_id="gid://shopify/Collection/1",
            title="Nouveautés",
        )
        self.assertIsNotNone(collection.pk)


class ProductModelTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="my-shop.myshopify.com",
            name="My Shop",
            access_token="shpat_token",
        )
        self.product = Product.objects.create(
            store=self.store,
            external_id="gid://shopify/Product/1",
            title="T-shirt",
        )

    def test_str_returns_title(self):
        self.assertEqual(str(self.product), "T-shirt")

    def test_unique_together_store_and_external_id(self):
        with self.assertRaises(IntegrityError):
            Product.objects.create(
                store=self.store,
                external_id="gid://shopify/Product/1",
                title="Duplicate",
            )

    def test_same_external_id_allowed_on_different_stores(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        product = Product.objects.create(
            store=other_store,
            external_id="gid://shopify/Product/1",
            title="T-shirt",
        )
        self.assertIsNotNone(product.pk)


class ProductVariantModelTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="my-shop.myshopify.com",
            name="My Shop",
            access_token="shpat_token",
        )
        self.product = Product.objects.create(
            store=self.store,
            external_id="gid://shopify/Product/1",
            title="T-shirt",
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            external_id="gid://shopify/ProductVariant/1",
            title="M / Rouge",
            price="29.99",
        )

    def test_str_returns_product_and_title(self):
        self.assertEqual(str(self.variant), "T-shirt - M / Rouge")

    def test_unique_together_product_and_external_id(self):
        with self.assertRaises(IntegrityError):
            ProductVariant.objects.create(
                product=self.product,
                external_id="gid://shopify/ProductVariant/1",
                title="Duplicate",
                price="9.99",
            )

    def test_same_external_id_allowed_on_different_products(self):
        other_product = Product.objects.create(
            store=self.store,
            external_id="gid://shopify/Product/2",
            title="Pantalon",
        )
        variant = ProductVariant.objects.create(
            product=other_product,
            external_id="gid://shopify/ProductVariant/1",
            title="M",
            price="49.99",
        )
        self.assertIsNotNone(variant.pk)
