from unittest.mock import patch

from django.test import TestCase

from core.business_logic.import_products import import_products
from core.models import Collection, Product, ProductVariant, Store

SHOPIFY_PRODUCTS = [
    {
        "id": "gid://shopify/Product/1",
        "title": "T-shirt",
        "collections": {"edges": [{"node": {"id": "gid://shopify/Collection/1", "title": "Nouveautés"}}]},
        "variants": {
            "edges": [{"node": {"id": "gid://shopify/ProductVariant/1", "title": "M / Rouge", "price": "29.99"}}]
        },
    }
]


class ImportProductsTest(TestCase):
    def setUp(self):
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
        )

    @patch("core.business_logic.import_products.get_product", return_value=SHOPIFY_PRODUCTS)
    def test_creates_product(self, _mock):
        import_products(self.store)

        self.assertEqual(Product.objects.filter(store=self.store).count(), 1)
        product = Product.objects.get(external_id="gid://shopify/Product/1")
        self.assertEqual(product.title, "T-shirt")

    @patch("core.business_logic.import_products.get_product", return_value=SHOPIFY_PRODUCTS)
    def test_upserts_existing_product(self, _mock):
        Product.objects.create(store=self.store, external_id="gid://shopify/Product/1", title="Old Title")

        import_products(self.store)

        self.assertEqual(Product.objects.filter(store=self.store).count(), 1)
        self.assertEqual(Product.objects.get(external_id="gid://shopify/Product/1").title, "T-shirt")

    @patch("core.business_logic.import_products.get_product", return_value=SHOPIFY_PRODUCTS)
    def test_creates_variant(self, _mock):
        import_products(self.store)

        variant = ProductVariant.objects.get(external_id="gid://shopify/ProductVariant/1")
        self.assertEqual(variant.title, "M / Rouge")
        self.assertEqual(str(variant.price), "29.99")

    @patch("core.business_logic.import_products.get_product", return_value=SHOPIFY_PRODUCTS)
    def test_upserts_existing_variant(self, _mock):
        product = Product.objects.create(store=self.store, external_id="gid://shopify/Product/1", title="T-shirt")
        ProductVariant.objects.create(
            product=product, external_id="gid://shopify/ProductVariant/1", title="Old", price="9.99"
        )

        import_products(self.store)

        variant = ProductVariant.objects.get(external_id="gid://shopify/ProductVariant/1")
        self.assertEqual(variant.title, "M / Rouge")
        self.assertEqual(str(variant.price), "29.99")

    @patch("core.business_logic.import_products.get_product", return_value=SHOPIFY_PRODUCTS)
    def test_creates_collection(self, _mock):
        import_products(self.store)

        collection = Collection.objects.get(external_id="gid://shopify/Collection/1")
        self.assertEqual(collection.title, "Nouveautés")

    @patch("core.business_logic.import_products.get_product", return_value=SHOPIFY_PRODUCTS)
    def test_upserts_existing_collection(self, _mock):
        Collection.objects.create(store=self.store, external_id="gid://shopify/Collection/1", title="Old")

        import_products(self.store)

        self.assertEqual(Collection.objects.filter(store=self.store).count(), 1)
        self.assertEqual(Collection.objects.get(external_id="gid://shopify/Collection/1").title, "Nouveautés")

    @patch("core.business_logic.import_products.get_product", return_value=SHOPIFY_PRODUCTS)
    def test_sets_product_collections(self, _mock):
        import_products(self.store)

        product = Product.objects.get(external_id="gid://shopify/Product/1")
        self.assertIn("Nouveautés", list(product.collections.values_list("title", flat=True)))

    @patch("core.business_logic.import_products.get_product")
    def test_removes_stale_collection_from_product(self, mock_get):
        mock_get.return_value = SHOPIFY_PRODUCTS
        import_products(self.store)

        mock_get.return_value = [{**SHOPIFY_PRODUCTS[0], "collections": {"edges": []}}]
        import_products(self.store)

        product = Product.objects.get(external_id="gid://shopify/Product/1")
        self.assertEqual(product.collections.count(), 0)

    @patch("core.business_logic.import_products.get_product")
    def test_handles_multiple_products(self, mock_get):
        mock_get.return_value = [
            SHOPIFY_PRODUCTS[0],
            {
                "id": "gid://shopify/Product/2",
                "title": "Pantalon",
                "collections": {"edges": []},
                "variants": {
                    "edges": [{"node": {"id": "gid://shopify/ProductVariant/2", "title": "L", "price": "49.99"}}]
                },
            },
        ]

        import_products(self.store)

        self.assertEqual(Product.objects.filter(store=self.store).count(), 2)
        self.assertEqual(ProductVariant.objects.count(), 2)
