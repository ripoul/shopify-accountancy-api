from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Collection, Product, ProductVariant, Store


class BaseProductViewSetTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="strongpassword",
        )
        self.store = Store.objects.create(
            shop_domain="test.myshopify.com",
            name="Test Store",
            access_token="shpat_test",
        )
        assign_perm("can_manage", self.user, self.store)
        self._authenticate(self.user)

    def _authenticate(self, user):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": user.username, "password": "strongpassword"},
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def _create_product(self, title="T-shirt", external_id="gid://shopify/Product/1"):
        return Product.objects.create(store=self.store, external_id=external_id, title=title)

    def _create_variant(
        self,
        product,
        title="M",
        price="29.99",
        external_id="gid://shopify/ProductVariant/1",
        distributor_price=None,
    ):
        return ProductVariant.objects.create(
            product=product,
            external_id=external_id,
            title=title,
            price=price,
            distributor_price=distributor_price,
        )

    def _create_collection(self, title="Nouveautés", external_id="gid://shopify/Collection/1"):
        return Collection.objects.create(store=self.store, external_id=external_id, title=title)


class ProductViewSetTest(BaseProductViewSetTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("product-list", kwargs={"store_pk": self.store.pk})
        self.import_url = reverse("product-import-products", kwargs={"store_pk": self.store.pk})

    def test_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_store_without_permission_returns_403(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        url = reverse("product-list", kwargs={"store_pk": other_store.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("core.views.product.upsert_products")
    def test_import_products_returns_204(self, _mock):
        response = self.client.post(self.import_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    @patch("core.views.product.upsert_products")
    def test_import_products_calls_upsert_with_store(self, mock_import):
        self.client.post(self.import_url)
        mock_import.assert_called_once_with(self.store)

    def test_import_products_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.post(self.import_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_import_products_store_without_permission_returns_404(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        url = reverse("product-import-products", kwargs={"store_pk": other_store.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_products_for_store(self):
        self._create_product()
        response = self.client.get(self.url)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "T-shirt")

    def test_does_not_return_other_store_products(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        Product.objects.create(store=other_store, external_id="gid://shopify/Product/99", title="Autre")
        response = self.client.get(self.url)
        self.assertEqual(len(response.data["results"]), 0)

    def test_variants_nested_in_response(self):
        product = self._create_product()
        self._create_variant(product, title="M / Rouge", distributor_price="12.34")
        response = self.client.get(self.url)
        variants = response.data["results"][0]["variants"]
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0]["title"], "M / Rouge")
        self.assertEqual(variants[0]["price"], "29.99")
        self.assertEqual(variants[0]["distributor_price"], "12.34")

    def test_collections_as_list_of_names(self):
        product = self._create_product()
        collection = self._create_collection(title="Nouveautés")
        product.collections.add(collection)
        response = self.client.get(self.url)
        self.assertIn("Nouveautés", response.data["results"][0]["collections"])

    def test_filter_by_name(self):
        self._create_product(title="T-shirt", external_id="gid://shopify/Product/1")
        self._create_product(title="Pantalon", external_id="gid://shopify/Product/2")
        response = self.client.get(self.url, {"name": "shirt"})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "T-shirt")

    def test_filter_by_name_case_insensitive(self):
        self._create_product(title="T-shirt", external_id="gid://shopify/Product/1")
        self._create_product(title="Pantalon", external_id="gid://shopify/Product/2")
        response = self.client.get(self.url, {"name": "SHIRT"})
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_by_collection(self):
        p1 = self._create_product(title="T-shirt", external_id="gid://shopify/Product/1")
        self._create_product(title="Pantalon", external_id="gid://shopify/Product/2")
        collection = self._create_collection()
        p1.collections.add(collection)
        response = self.client.get(self.url, {"collection": collection.pk})
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "T-shirt")

    def test_ordering_by_name_asc(self):
        self._create_product(title="Zèbre", external_id="gid://shopify/Product/1")
        self._create_product(title="Abricot", external_id="gid://shopify/Product/2")
        response = self.client.get(self.url, {"ordering": "name"})
        titles = [r["title"] for r in response.data["results"]]
        self.assertEqual(titles[0], "Abricot")
        self.assertEqual(titles[1], "Zèbre")

    def test_ordering_by_name_desc(self):
        self._create_product(title="Zèbre", external_id="gid://shopify/Product/1")
        self._create_product(title="Abricot", external_id="gid://shopify/Product/2")
        response = self.client.get(self.url, {"ordering": "-name"})
        titles = [r["title"] for r in response.data["results"]]
        self.assertEqual(titles[0], "Zèbre")
        self.assertEqual(titles[1], "Abricot")

    def test_ordering_by_price_asc(self):
        p1 = self._create_product(title="Cheap", external_id="gid://shopify/Product/1")
        p2 = self._create_product(title="Expensive", external_id="gid://shopify/Product/2")
        self._create_variant(p1, price="10.00", external_id="gid://shopify/ProductVariant/1")
        self._create_variant(p2, price="100.00", external_id="gid://shopify/ProductVariant/2")
        response = self.client.get(self.url, {"ordering": "price"})
        titles = [r["title"] for r in response.data["results"]]
        self.assertEqual(titles, ["Cheap", "Expensive"])

    def test_ordering_by_price_desc(self):
        p1 = self._create_product(title="Cheap", external_id="gid://shopify/Product/1")
        p2 = self._create_product(title="Expensive", external_id="gid://shopify/Product/2")
        self._create_variant(p1, price="10.00", external_id="gid://shopify/ProductVariant/1")
        self._create_variant(p2, price="100.00", external_id="gid://shopify/ProductVariant/2")
        response = self.client.get(self.url, {"ordering": "-price"})
        titles = [r["title"] for r in response.data["results"]]
        self.assertEqual(titles, ["Expensive", "Cheap"])

    def test_ordering_by_collection_asc(self):
        p1 = self._create_product(title="T-shirt", external_id="gid://shopify/Product/1")
        p2 = self._create_product(title="Pantalon", external_id="gid://shopify/Product/2")
        c1 = self._create_collection(title="Zèbre", external_id="gid://shopify/Collection/1")
        c2 = self._create_collection(title="Alpha", external_id="gid://shopify/Collection/2")
        p1.collections.add(c1)
        p2.collections.add(c2)
        response = self.client.get(self.url, {"ordering": "collection"})
        titles = [r["title"] for r in response.data["results"]]
        self.assertEqual(titles, ["Pantalon", "T-shirt"])

    def test_ordering_by_collection_desc(self):
        p1 = self._create_product(title="T-shirt", external_id="gid://shopify/Product/1")
        p2 = self._create_product(title="Pantalon", external_id="gid://shopify/Product/2")
        c1 = self._create_collection(title="Zèbre", external_id="gid://shopify/Collection/1")
        c2 = self._create_collection(title="Alpha", external_id="gid://shopify/Collection/2")
        p1.collections.add(c1)
        p2.collections.add(c2)
        response = self.client.get(self.url, {"ordering": "-collection"})
        titles = [r["title"] for r in response.data["results"]]
        self.assertEqual(titles, ["T-shirt", "Pantalon"])


class CollectionViewSetTest(BaseProductViewSetTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("collection-list", kwargs={"store_pk": self.store.pk})

    def test_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_store_without_permission_returns_403(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        url = reverse("collection-list", kwargs={"store_pk": other_store.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_collections_for_store(self):
        self._create_collection(title="Nouveautés")
        response = self.client.get(self.url)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "Nouveautés")

    def test_does_not_return_other_store_collections(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        Collection.objects.create(store=other_store, external_id="gid://shopify/Collection/99", title="Autre")
        response = self.client.get(self.url)
        self.assertEqual(len(response.data["results"]), 0)

    def test_ordered_by_title(self):
        self._create_collection(title="Zèbre", external_id="gid://shopify/Collection/1")
        self._create_collection(title="Alpha", external_id="gid://shopify/Collection/2")
        response = self.client.get(self.url)
        titles = [r["title"] for r in response.data["results"]]
        self.assertEqual(titles, sorted(titles))

    def test_response_contains_external_id(self):
        self._create_collection(title="Nouveautés", external_id="gid://shopify/Collection/1")
        response = self.client.get(self.url)
        self.assertIn("external_id", response.data["results"][0])
