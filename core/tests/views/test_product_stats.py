import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import make_aware
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient

from core.models import Collection, Order, OrderLineItem, Product, ProductVariant, Store


class BaseProductStatsTestCase(TestCase):
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

    def _create_variant(self, product, external_id="gid://shopify/ProductVariant/1"):
        return ProductVariant.objects.create(
            product=product,
            external_id=external_id,
            title="Default",
            price=Decimal("29.99"),
        )

    def _create_order(self, external_id="gid://shopify/Order/1"):
        return Order.objects.create(
            store=self.store,
            external_id=external_id,
            name=f"#{external_id[-1]}",
            processed_at=make_aware(datetime.datetime(2025, 1, 10)),
            total_price=Decimal("100.00"),
        )

    def _create_line_item(
        self,
        order,
        product,
        variant=None,
        unit_price="30.00",
        distributor_price="10.00",
        quantity=1,
        external_id="gid://shopify/LineItem/1",
    ):
        return OrderLineItem.objects.create(
            order=order,
            product=product,
            variant=variant,
            external_id=external_id,
            title=product.title,
            unit_price=Decimal(unit_price),
            distributor_price=Decimal(distributor_price),
            quantity=quantity,
        )


class ProductStatsViewSetTest(BaseProductStatsTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("stat-product-stats", kwargs={"store_pk": self.store.pk})

    def test_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_returns_401(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_store_without_permission_returns_403(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        url = reverse("stat-product-stats", kwargs={"store_pk": other_store.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_response_fields_present(self):
        self._create_product()
        response = self.client.get(self.url)
        expected_fields = {
            "id",
            "external_id",
            "title",
            "total_sold",
            "net_gain",
            "net_gain_per_unit",
            "orders_containing",
            "occurrence_rate",
        }
        self.assertEqual(set(response.data[0].keys()), expected_fields)

    def test_product_without_sales_has_zero_stats(self):
        self._create_product()
        response = self.client.get(self.url)
        result = response.data[0]
        self.assertEqual(result["total_sold"], 0)
        self.assertEqual(result["net_gain"], "0.00")
        self.assertEqual(result["net_gain_per_unit"], "0.00")
        self.assertEqual(result["orders_containing"], 0)
        self.assertEqual(result["occurrence_rate"], "0.0000")

    def test_total_sold_aggregates_all_variants(self):
        # Line items from two different variants of the same product
        product = self._create_product()
        v1 = self._create_variant(product, external_id="gid://shopify/ProductVariant/1")
        v2 = ProductVariant.objects.create(
            product=product, external_id="gid://shopify/ProductVariant/2", title="L", price=Decimal("29.99")
        )
        order = self._create_order()
        self._create_line_item(order, product, variant=v1, quantity=3, external_id="gid://shopify/LineItem/1")
        self._create_line_item(order, product, variant=v2, quantity=4, external_id="gid://shopify/LineItem/2")
        response = self.client.get(self.url)
        self.assertEqual(response.data[0]["total_sold"], 7)

    def test_net_gain_total(self):
        # (30 - 10) * 2 = 40
        product = self._create_product()
        variant = self._create_variant(product)
        order = self._create_order()
        self._create_line_item(
            order, product, variant=variant, unit_price="30.00", distributor_price="10.00", quantity=2
        )  # noqa: E501
        response = self.client.get(self.url)
        self.assertEqual(response.data[0]["net_gain"], "40.00")

    def test_net_gain_accumulated_across_orders(self):
        # order1: (30-10)*2=40; order2: (50-20)*1=30; total=70
        product = self._create_product()
        variant = self._create_variant(product)
        order1 = self._create_order(external_id="gid://shopify/Order/1")
        order2 = self._create_order(external_id="gid://shopify/Order/2")
        self._create_line_item(
            order1,
            product,
            variant=variant,
            unit_price="30.00",
            distributor_price="10.00",
            quantity=2,
            external_id="gid://shopify/LineItem/1",
        )
        self._create_line_item(
            order2,
            product,
            variant=variant,
            unit_price="50.00",
            distributor_price="20.00",
            quantity=1,
            external_id="gid://shopify/LineItem/2",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.data[0]["net_gain"], "70.00")

    def test_net_gain_per_unit(self):
        # gain=40, sold=2 → per_unit=20
        product = self._create_product()
        variant = self._create_variant(product)
        order = self._create_order()
        self._create_line_item(
            order, product, variant=variant, unit_price="30.00", distributor_price="10.00", quantity=2
        )
        response = self.client.get(self.url)
        self.assertEqual(response.data[0]["net_gain_per_unit"], "20.00")

    def test_net_gain_per_unit_zero_when_no_sales(self):
        self._create_product()
        response = self.client.get(self.url)
        self.assertEqual(response.data[0]["net_gain_per_unit"], "0.00")

    def test_orders_containing_counts_distinct_orders(self):
        product = self._create_product()
        variant = self._create_variant(product)
        order = self._create_order()
        # Two line items in the same order → still 1 order containing this product
        self._create_line_item(order, product, variant=variant, external_id="gid://shopify/LineItem/1")
        self._create_line_item(order, product, variant=variant, external_id="gid://shopify/LineItem/2")
        response = self.client.get(self.url)
        self.assertEqual(response.data[0]["orders_containing"], 1)

    def test_orders_containing_counts_multiple_orders(self):
        product = self._create_product()
        variant = self._create_variant(product)
        order1 = self._create_order(external_id="gid://shopify/Order/1")
        order2 = self._create_order(external_id="gid://shopify/Order/2")
        self._create_line_item(order1, product, variant=variant, external_id="gid://shopify/LineItem/1")
        self._create_line_item(order2, product, variant=variant, external_id="gid://shopify/LineItem/2")
        response = self.client.get(self.url)
        self.assertEqual(response.data[0]["orders_containing"], 2)

    def test_occurrence_rate_calculated_correctly(self):
        # product in 2 out of 3 orders → 2/3 ≈ 0.6667
        product = self._create_product()
        variant = self._create_variant(product)
        order1 = self._create_order(external_id="gid://shopify/Order/1")
        order2 = self._create_order(external_id="gid://shopify/Order/2")
        self._create_order(external_id="gid://shopify/Order/3")
        self._create_line_item(order1, product, variant=variant, external_id="gid://shopify/LineItem/1")
        self._create_line_item(order2, product, variant=variant, external_id="gid://shopify/LineItem/2")
        response = self.client.get(self.url)
        self.assertEqual(response.data[0]["occurrence_rate"], "0.6667")

    def test_occurrence_rate_zero_when_no_orders(self):
        self._create_product()
        response = self.client.get(self.url)
        self.assertEqual(response.data[0]["occurrence_rate"], "0.0000")

    def test_occurrence_rate_one_when_in_all_orders(self):
        product = self._create_product()
        variant = self._create_variant(product)
        order = self._create_order()
        self._create_line_item(order, product, variant=variant)
        response = self.client.get(self.url)
        self.assertEqual(response.data[0]["occurrence_rate"], "1.0000")

    def test_products_counted_independently(self):
        p1 = self._create_product(title="A", external_id="gid://shopify/Product/1")
        p2 = self._create_product(title="B", external_id="gid://shopify/Product/2")
        v1 = self._create_variant(p1, external_id="gid://shopify/ProductVariant/1")
        v2 = self._create_variant(p2, external_id="gid://shopify/ProductVariant/2")
        order = self._create_order()
        self._create_line_item(order, p1, variant=v1, quantity=3, external_id="gid://shopify/LineItem/1")
        self._create_line_item(order, p2, variant=v2, quantity=7, external_id="gid://shopify/LineItem/2")
        response = self.client.get(self.url)
        sold_by_title = {r["title"]: r["total_sold"] for r in response.data}
        self.assertEqual(sold_by_title["A"], 3)
        self.assertEqual(sold_by_title["B"], 7)

    def test_store_isolation(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        other_product = Product.objects.create(store=other_store, external_id="gid://shopify/Product/99", title="Alien")
        other_variant = ProductVariant.objects.create(
            product=other_product, external_id="gid://shopify/ProductVariant/99", title="XL", price=Decimal("50.00")
        )
        other_order = Order.objects.create(
            store=other_store,
            external_id="gid://shopify/Order/99",
            name="#99",
            processed_at=make_aware(datetime.datetime(2025, 1, 10)),
            total_price=Decimal("100.00"),
        )
        OrderLineItem.objects.create(
            order=other_order,
            product=other_product,
            variant=other_variant,
            external_id="gid://shopify/LineItem/99",
            title="XL",
            unit_price=Decimal("100.00"),
            distributor_price=Decimal("50.00"),
            quantity=10,
        )
        self._create_product()
        response = self.client.get(self.url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["total_sold"], 0)

    def test_does_not_return_other_store_products(self):
        other_store = Store.objects.create(shop_domain="other.myshopify.com", name="Other", access_token="shpat_other")
        Product.objects.create(store=other_store, external_id="gid://shopify/Product/99", title="Alien")
        response = self.client.get(self.url)
        self.assertEqual(len(response.data), 0)

    def test_filter_by_name(self):
        self._create_product(title="T-shirt", external_id="gid://shopify/Product/1")
        self._create_product(title="Pantalon", external_id="gid://shopify/Product/2")
        response = self.client.get(self.url, {"name": "shirt"})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "T-shirt")

    def test_filter_by_name_case_insensitive(self):
        self._create_product(title="T-shirt", external_id="gid://shopify/Product/1")
        self._create_product(title="Pantalon", external_id="gid://shopify/Product/2")
        response = self.client.get(self.url, {"name": "SHIRT"})
        self.assertEqual(len(response.data), 1)

    def test_filter_by_collection(self):
        p1 = self._create_product(title="T-shirt", external_id="gid://shopify/Product/1")
        self._create_product(title="Pantalon", external_id="gid://shopify/Product/2")
        collection = Collection.objects.create(store=self.store, external_id="gid://shopify/Collection/1", title="Tops")
        p1.collections.add(collection)
        response = self.client.get(self.url, {"collection": collection.pk})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "T-shirt")
